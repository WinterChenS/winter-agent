from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import settings
from core.runtime import get_tool_registry
from domain.capability import CapabilityCall
from graph.normalizers.tool_result import (
    normalize_tool_result_for_prompt,
    normalize_tool_step_record,
)
from graph.state import State
from policy.gate import PolicyGate
from policy.models import PolicyContext

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# ReAct 提示词：引导 LLM 按照 Thought → Action → Observation 循环解决问题
# ────────────────────────────────────────────────────────────────────────────
_REACT_SYSTEM_PROMPT = """\
You are a ReAct agent. Your response MUST be a single valid JSON object.

[Internal Cycle: Thought → Action → Observation → Final Answer]

CRITICAL: Output ONLY the JSON object. No markdown wrapping, no explanation.

Tool call format:
{"action":"tool","tool":"<name>","query":"<query>"}

Final answer ready (data collection complete):
{"action":"final_answer"}

Available tools:
- search: web search. Returns titles, URLs, and content snippets.
- browser: open a URL and read its content. MUST use exact URL from search results. Never fabricate URLs.
- time: get current date/time. Use for time-related questions.

Rules:
1. Output ONLY the JSON. No other text.
2. After search results, use browser to read at least one relevant page before concluding.
3. If browser returns an error, fall back to using search snippets — do NOT retry browser.
4. Call final_answer only when you have sufficient information to answer the user's question fully.
"""


def _max_iterations() -> int:
    return max(1, int(getattr(settings, "max_tool_iterations", 5) or 5))


MAX_ITERATIONS = _max_iterations()


def _max_consecutive_search_calls() -> int:
    return max(1, int(getattr(settings, "max_consecutive_search_calls", 2) or 2))


def _build_policy_gate() -> PolicyGate:
    raw = (settings.policy_tool_whitelist or "").strip()
    whitelist = {x.strip() for x in raw.split(",") if x.strip()} if raw else set()
    max_query_len = max(1, int(settings.policy_max_query_len or 500))
    timeout_override_ms = int(settings.policy_timeout_override_ms or 0) or None
    return PolicyGate(
        tool_whitelist=whitelist,
        max_query_len=max_query_len,
        timeout_override_ms=timeout_override_ms,
    )


def _error_text(error: object) -> str:
    if isinstance(error, dict):
        message = error.get("message") or error.get("error") or error.get("code")
        return str(message or "unknown error")
    if error is None:
        return "unknown error"
    return str(error)


def _reason_record(node: str, code: str, message: str, extra: dict | None = None) -> dict:
    record = {
        "node": node,
        "code": code,
        "message": message,
        "timestamp": int(time.time() * 1000),
    }
    if extra:
        record["extra"] = extra
    return record


def _append_reason(state: State, record: dict) -> list:
    return list(state.get("reasoning_steps", [])) + [record]


def _build_llm(streaming: bool = True, json_mode: bool = False) -> ChatOpenAI:
    kwargs = {
        "model": settings.model,
        "temperature": 0.3 if json_mode else settings.temperature,
        "streaming": streaming,
        "api_key": settings.api_key,
        "base_url": settings.base_url,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return ChatOpenAI(**kwargs)


def _force_final_answer(state: State, tool_result: str | None,
                         reason: dict | None = None) -> dict:
    """Force transition to chart_planner when guardrails trigger."""
    record = reason or _reason_record("agent_node", "FORCED_FINAL",
        "Forcing transition to chart planner.")
    return {
        "current_tool": None,
        "tool_input": None,
        "tool_result": None,
        "last_tool_name": None,
        "last_tool_query": None,
        "consecutive_search_count": 0,
        "last_guard_reason": record,
        "reasoning_steps": _append_reason(state, record),
        "route": "chart_planner",
    }


# ────────────────────────────────────────────────────────────────────────────
# agent_node：LLM 决策节点（JSON Mode）
# ────────────────────────────────────────────────────────────────────────────
async def agent_node(state: State) -> dict:
    registry = get_tool_registry()

    # 1. Build tool list description
    tools_desc = ""
    if registry:
        for t in registry.list_tools():
            tools_desc += f"  - {t['name']}: {t['description']}\n"

    # 2. Build system prompt with Observation
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    tool_result = state.get("tool_result")
    tool_result_sanitized = normalize_tool_result_for_prompt(tool_result)
    current_iteration = int(state.get("iteration_count", 0) or 0)

    system_lines = [
        _REACT_SYSTEM_PROMPT,
        f"Current server time: {now_str}",
    ]
    if tools_desc:
        system_lines.append(f"Available tools:\n{tools_desc}")

    if tool_result_sanitized:
        remaining = MAX_ITERATIONS - current_iteration
        system_lines.append(
            f"\n--- Observation (iteration {current_iteration}/{MAX_ITERATIONS}) ---\n"
            f"{tool_result_sanitized}\n"
            "--- End Observation ---\n"
        )
        system_lines.append(
            "Continue the ReAct cycle: if you need more info, call another tool. "
            f"Otherwise, output final_answer. ({remaining} iterations remaining)"
        )

    system_prompt = "\n".join(system_lines)

    # 3. Call LLM with JSON Mode
    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    llm = _build_llm(streaming=False, json_mode=True)

    try:
        response = await llm.ainvoke(messages)
        content = (response.content or "").strip()
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("agent_node: JSON parse failed, forcing final answer: %s", e)
        return _force_final_answer(state, tool_result)

    action = str(parsed.get("action", "")).strip().lower()

    # 4. Handle tool call
    if action == "tool":
        tool_name = str(parsed.get("tool", "")).strip().lower()
        query = str(parsed.get("query", "")).strip()

        if not tool_name:
            return _force_final_answer(state, tool_result)

        normalized_query = _normalize_query(query)
        consecutive_search_count = int(state.get("consecutive_search_count", 0) or 0)
        next_consecutive = consecutive_search_count + 1 if tool_name == "search" else 0

        # Guard: max iterations
        if current_iteration >= MAX_ITERATIONS:
            reason = _reason_record("agent_node", "MAX_ITERATIONS_REACHED",
                f"Iteration limit ({MAX_ITERATIONS}) reached; forcing final answer.")
            return _force_final_answer(state, tool_result, reason)

        # Guard: duplicate tool call
        last_tool_name = (state.get("last_tool_name") or "").strip().lower()
        last_tool_query = _normalize_query(str(state.get("last_tool_query") or ""))
        if last_tool_name == tool_name and last_tool_query == normalized_query:
            reason = _reason_record("agent_node", "DUPLICATE_TOOL_CALL_BLOCKED",
                f"Blocked duplicate: tool='{tool_name}', query='{query}'.",
                extra={"tool": tool_name, "query": query})
            return _force_final_answer(state, tool_result, reason)

        # Guard: max consecutive search
        max_search = _max_consecutive_search_calls()
        if tool_name == "search" and next_consecutive > max_search:
            reason = _reason_record("agent_node", "MAX_CONSECUTIVE_SEARCH_REACHED",
                f"Consecutive search limit ({max_search}) reached; forcing final answer.",
                extra={"count": next_consecutive, "limit": max_search})
            return _force_final_answer(state, tool_result, reason)

        reason = _reason_record("agent_node", "TOOL_CALL_DECIDED",
            f"Tool call: '{tool_name}' query='{query}'", extra={"tool": tool_name})
        return {
            "current_tool": tool_name,
            "tool_input": {"query": query},
            "tool_result": None,
            "iteration_count": current_iteration + 1,
            "last_tool_name": tool_name,
            "last_tool_query": query,
            "consecutive_search_count": next_consecutive,
            "reasoning_steps": _append_reason(state, reason),
            "route": "tool",
        }

    # 5. Handle final_answer
    if action == "final_answer":
        reason = _reason_record("agent_node", "FINAL_ANSWER",
            "Agent decided data collection is complete.")
        return {
            "current_tool": None,
            "tool_input": None,
            "tool_result": None,
            "last_tool_name": None,
            "last_tool_query": None,
            "consecutive_search_count": 0,
            "reasoning_steps": _append_reason(state, reason),
            "route": "chart_planner",
        }

    # Unknown action → force final
    logger.warning("agent_node: unknown action '%s', forcing final answer", action)
    return _force_final_answer(state, tool_result)


# ────────────────────────────────────────────────────────────────────────────
# tool_node：工具执行节点
# ────────────────────────────────────────────────────────────────────────────
async def tool_node(state: State) -> dict:
    tool_name = state.get("current_tool") or ""
    tool_input = state.get("tool_input") or {}
    start_time = time.time()
    gate = _build_policy_gate()
    call = CapabilityCall(capability_name=tool_name, input_payload=tool_input)

    decision = gate.evaluate(
        call,
        context=PolicyContext(
            conversation_id=str(state.get("conversation_id") or ""),
            agent_id=str(state.get("active_agent") or "agent.main"),
        ),
    )

    if decision.action != "allow":
        result = {
            "ok": False,
            "error": {
                "code": decision.code or "POLICY_DENIED",
                "message": decision.reason or "Blocked by policy gate",
                "retryable": False,
            },
        }
        result_str = json.dumps(result, ensure_ascii=False)
        step = f"[tool_node] Policy denied capability '{tool_name}': {decision.reason or decision.code}"
        status = "error"
        error_msg = _error_text(result.get("error"))
    else:
        registry = get_tool_registry()
        if not registry:
            result = {"ok": False, "error": "ToolRegistry not initialized", "code": "REGISTRY_NOT_READY"}
            result_str = json.dumps(result, ensure_ascii=False)
            step = f"[tool_node] ERROR: registry not available, skipped '{tool_name}'"
            status = "error"
            error_msg = "ToolRegistry not initialized"
        else:
            try:
                timeout_ms = gate.timeout_override_ms
                if timeout_ms and timeout_ms > 0:
                    result = await asyncio.wait_for(
                        registry.invoke_capability(call),
                        timeout=timeout_ms / 1000,
                    )
                else:
                    result = await registry.invoke_capability(call)
            except asyncio.TimeoutError:
                result = {
                    "ok": False,
                    "error": {
                        "code": "TOOL_TIMEOUT",
                        "message": "tool invocation timeout",
                        "retryable": True,
                    },
                }
            except Exception as exc:
                logger.exception("tool_node invoke failed for tool=%s", tool_name)
                result = {
                    "ok": False,
                    "error": {
                        "code": "TOOL_INVOKE_EXCEPTION",
                        "message": f"tool invoke exception: {str(exc)[:200]}",
                        "retryable": False,
                    },
                }

            result_str = json.dumps(result, ensure_ascii=False)
            ok = bool(result.get("ok", False))
            status = "completed" if ok else "error"
            error_msg = _error_text(result.get("error")) if not ok else None
            step = (
                f"[tool_node] Tool '{tool_name}' executed successfully."
                if ok
                else f"[tool_node] Tool '{tool_name}' returned error: {error_msg}"
            )

    elapsed_time = time.time() - start_time
    tool_step_record = normalize_tool_step_record(
        tool_name=tool_name,
        tool_input=tool_input,
        status=status,
        elapsed_ms=int(elapsed_time * 1000),
        timestamp=start_time,
        error=error_msg,
    )

    new_tool_steps = state.get("tool_steps", []) + [tool_step_record]

    return {
        "tool_result": result_str,
        "tool_steps": new_tool_steps,
        "current_tool": None,
        "tool_input": None,
        "last_tool_name": None,
        "last_tool_query": None,
        "reasoning_steps": state.get("reasoning_steps", []) + [step],
        "route": "agent",
    }


def _normalize_query(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


# ────────────────────────────────────────────────────────────────────────────
# chart_node：图表规划 + 生成 + 内容编排节点
# ────────────────────────────────────────────────────────────────────────────
async def chart_node(state: State) -> dict:
    """Pass-through: chart_specs generated inline by generate_chart tool during loop."""
    chart_specs = state.get("chart_specs", [])
    blocks = []
    for cs in chart_specs:
        blocks.append({"type": "chart", "chart_spec": cs})
    return {
        "chart_specs": chart_specs,
        "blocks": blocks,
    }


# ────────────────────────────────────────────────────────────────────────────
# chart_planner_node：JSON Mode 图表规划（阶段二）
# ────────────────────────────────────────────────────────────────────────────
_CHART_PLANNER_SYSTEM_PROMPT = """\
You are a data analyst. Analyze the conversation below and extract chart-worthy numerical data.
Output a single valid JSON object. No markdown wrapping.

{
  "charts": [
    {
      "id": 0,
      "chart_type": "bar",
      "title": "Chart Title",
      "description": "What this chart shows",
      "x_axis_label": "X Label",
      "y_axis_label": "Y Label",
      "data": [
        {"name": "Item A", "value": 123},
        {"name": "Item B", "value": 456}
      ]
    }
  ]
}

Rules:
- chart_type: line | bar | pie | scatter | area | radar
- id: sequential integer starting from 0
- data: maximum 20 data points
- pie chart: do NOT set x_axis_label or y_axis_label
- Extract data from tool results first. If no tool data exists, use your own knowledge
- Do NOT fabricate numbers — only use data you are confident about
- If there is NO numerical data suitable for charts, return {"charts": []}
- When the user explicitly asks for a chart (柱状图/图表/bar/pie/line chart etc.), you MUST return at least one chart if ANY relevant numerical data exists
"""


async def chart_planner_node(state: State) -> dict:
    """Phase 2: Extract chart data from conversation context using JSON Mode."""
    from graph.validators import validate_chart_specs

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    system_content = _CHART_PLANNER_SYSTEM_PROMPT
    if now_str:
        system_content += f"\nCurrent time: {now_str}"

    messages = [SystemMessage(content=system_content)] + list(state["messages"])

    llm = _build_llm(streaming=False, json_mode=True)
    llm.temperature = 0.1  # Override for precision — chart data extraction needs accuracy

    try:
        response = await llm.ainvoke(messages)
        result = json.loads(response.content)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("chart_planner_node: JSON parse failed: %s", e)
        result = {"charts": []}

    raw_charts = result.get("charts", [])
    if not isinstance(raw_charts, list):
        raw_charts = []

    validated = validate_chart_specs(raw_charts)

    return {
        "chart_specs": validated,
        "route": "answer",
    }


# ────────────────────────────────────────────────────────────────────────────
# answer_node：Normal Mode 流式最终答案（阶段三）
# ────────────────────────────────────────────────────────────────────────────
_ANSWER_SYSTEM_PROMPT_TEMPLATE = """\
You are a helpful AI assistant. Answer the user's question based on the research results.
Use Markdown for formatting and structure.

{chart_section}

[Output Instructions]
- When your analysis reaches a point where a chart helps, reference it with [CHART:n] on its own line
- Each available chart MUST be referenced at least once
- When you reference a chart, do NOT repeat all its data values as text — let the chart show them
- Write naturally as if the chart is embedded in your response
- NEVER say "I cannot generate charts" or "I am unable to create charts" — if no charts are listed above, simply answer without referring to charts
- Keep answers concise and well-structured
- Reply in the same language as the user's question

Current time: {now_str}
"""


def _build_chart_section(chart_specs: list) -> str:
    """Build the chart description section for the answer prompt."""
    if not chart_specs:
        return "[Available Charts]\nNone. Answer without referencing any charts."

    lines = ["[Available Charts]"]
    for c in chart_specs:
        if not isinstance(c, dict):
            continue
        cid = c.get("id", "?")
        ctype = c.get("chartType", "bar")
        title = c.get("title", "Untitled")
        desc = c.get("description", "")
        x_label = c.get("xAxisLabel", "")
        y_label = c.get("yAxisLabel", "")
        data_count = len(c.get("data", []))
        lines.append(
            f"  Chart {cid} ({ctype}): \"{title}\" — {desc} "
            f"({data_count} data points, x={x_label}, y={y_label})"
        )
    return "\n".join(lines)


async def answer_node(state: State) -> dict:
    """Phase 3: Generate streaming final answer with [CHART:n] markers."""
    chart_specs = list(state.get("chart_specs", []) or [])
    chart_section = _build_chart_section(chart_specs)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    system_content = _ANSWER_SYSTEM_PROMPT_TEMPLATE.format(
        chart_section=chart_section,
        now_str=now_str,
    )

    messages = [SystemMessage(content=system_content)] + list(state["messages"])

    llm = _build_llm(streaming=True, json_mode=False)

    try:
        response = await llm.ainvoke(messages)
    except Exception as exc:
        logger.exception("answer_node: LLM invoke failed")
        fallback = "Sorry, an error occurred while generating the answer. Please try again."
        return {
            "messages": [AIMessage(content=fallback)],
            "chart_specs": chart_specs,
            "route": "end",
        }

    return {
        "messages": [response],
        "chart_specs": chart_specs,
        "route": "end",
    }
