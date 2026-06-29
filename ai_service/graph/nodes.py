from __future__ import annotations

import asyncio
import json
import logging
import re
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

Tool call (single): {"action":"tool","tool":"<name>","query":"<query>"}
Tool call (parallel): {"actions":[{"tool":"...","query":"..."}, ...]} — max 3

Final answer ready (data collection complete):
{"action":"final_answer"}

Available tools:
- search: web search. Returns titles, URLs, and content snippets.
- browser: open a URL and read its content. MUST use exact URL from search results. Never fabricate URLs.
- time: get current date/time. Use for time-related questions.

Rules:
1. Output ONLY the JSON object. No other text — no markdown, no explanation.
2. For questions involving facts, data, statistics, numbers, or real-world information, you MUST call search first — never answer from training data alone.
3. After search returns results, open at least one URL with browser to read the actual content.
4. If browser returns an error, use search snippets directly — do NOT retry browser.
5. Call final_answer ONLY after you have collected evidence via tools. If you haven't used any tools, do NOT output final_answer.
6. Use parallel format when you need multiple independent pieces of information at the same time.
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
    active = state.get("active_agent", "default")
    logging.info("[AGENT_NODE] active_agent=%s iteration=%s", active, state.get("iteration_count", 0))

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
    else:
        # First iteration: force tool call unless it's a trivial greeting
        system_lines.append(
            f"\nIMPORTANT: Your training data cutoff is before {now_str}. "
            "For factual, statistical, or data-related questions, your knowledge is likely outdated. "
            "You are on iteration 1. Unless the user's question is PURELY a simple greeting "
            "(like 'hello' or 'how are you'), you MUST call a tool (search/browser/time) first. "
            "final_answer is NOT allowed on this turn — output a tool-call JSON instead."
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

    # 4a. Handle parallel tool calls (new format)
    if "actions" in parsed and isinstance(parsed["actions"], list):
        actions = parsed["actions"][:3]
        if not actions:
            return _force_final_answer(state, tool_result)

        # Guard: max iterations
        if current_iteration >= MAX_ITERATIONS:
            reason = _reason_record("agent_node", "MAX_ITERATIONS_REACHED",
                f"Iteration limit ({MAX_ITERATIONS}) reached; forcing final answer.")
            return _force_final_answer(state, tool_result, reason)

        first_tool_name = str(actions[0].get("tool", "")).strip().lower()
        if not first_tool_name:
            return _force_final_answer(state, tool_result)

        # Count consecutive searches from all parallel actions
        consecutive_search_count = int(state.get("consecutive_search_count", 0) or 0)
        parallel_search_count = sum(1 for a in actions if str(a.get("tool", "")).strip().lower() == "search")
        next_consecutive = consecutive_search_count + parallel_search_count if parallel_search_count > 0 else 0

        # Guard: max consecutive search
        max_search = _max_consecutive_search_calls()
        search_extra = {"parallel_search_count": parallel_search_count, "consecutive_search_count": next_consecutive, "limit": max_search}
        if parallel_search_count > 0 and next_consecutive > max_search:
            reason = _reason_record("agent_node", "MAX_CONSECUTIVE_SEARCH_REACHED",
                f"Consecutive search limit ({max_search}) reached in parallel call; forcing final answer.",
                extra=search_extra)
            return _force_final_answer(state, tool_result, reason)

        reason = _reason_record("agent_node", "PARALLEL_TOOL_CALL",
            f"Parallel tool call: {len(actions)} tools",
            extra={"tools": [a.get("tool") for a in actions]})
        return {
            "current_tool": first_tool_name,
            "tool_input": {"actions": actions},
            "tool_result": None,
            "iteration_count": current_iteration + 1,
            "last_tool_name": first_tool_name,
            "last_tool_query": str(actions[0].get("query", "")).strip(),
            "consecutive_search_count": next_consecutive,
            "reasoning_steps": _append_reason(state, reason),
            "route": "tool",
        }

    action = str(parsed.get("action", "")).strip().lower()

    # 4b. Handle tool call
    if action == "tool":
        tool_name = str(parsed.get("tool", "")).strip().lower()
        query = str(parsed.get("query", "")).strip()
        logging.info("[AGENT_NODE] 🛠️ tool call decision: tool=%s query=%s", tool_name, query[:80])

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

    # 5. Handle final_answer — reject on first iteration
    if action == "final_answer":
        logging.info("[AGENT_NODE] LLM returned final_answer (iter=%s, has_tool_result=%s)", current_iteration, bool(tool_result_sanitized))
        if not tool_result_sanitized:
            logging.warning("[AGENT_NODE] ⚠️ final_answer on first turn — auto-injecting forced search")
            # First iteration with no tools → force search with user's question
            user_query = ""
            raw_messages = list(state.get("messages") or [])
            for msg in reversed(raw_messages):
                if hasattr(msg, "type") and msg.type == "human":
                    user_query = (msg.content or "")[:200]
                    break
                if isinstance(msg, dict) and msg.get("role") in ("user", "human"):
                    user_query = str(msg.get("content", ""))[:200]
                    break
            reason = _reason_record("agent_node", "FIRST_TURN_FORCED_SEARCH",
                "LLM attempted final_answer without tools; auto-injecting search.",
                extra={"user_query": user_query[:100]})
            return {
                "current_tool": "search",
                "tool_input": {"query": user_query or "latest information"},
                "tool_result": None,
                "iteration_count": current_iteration + 1,
                "last_tool_name": "search",
                "last_tool_query": user_query,
                "consecutive_search_count": 1,
                "reasoning_steps": _append_reason(state, reason),
                "route": "tool",
            }
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
# _execute_single_tool：执行单个工具并返回结果 + 计时元数据
# ────────────────────────────────────────────────────────────────────────────
async def _execute_single_tool(
    tool_name: str,
    tool_input: dict,
    gate: PolicyGate,
    context: PolicyContext,
) -> dict:
    """Execute a single tool, return dict with 'result', 'elapsed_ms', 'status', 'error_msg'."""
    # Normalize tool_input: map "query" to the tool's first required param if different
    registry = get_tool_registry()
    if registry and "query" in tool_input:
        try:
            tool = registry.get(tool_name)
            schema_params = getattr(tool, "schema", None)
            if schema_params and isinstance(schema_params.parameters, dict):
                required = schema_params.parameters.get("required", [])
                if required and required[0] != "query" and required[0] not in tool_input:
                    tool_input = {required[0]: tool_input["query"]}
        except Exception:
            pass
    call = CapabilityCall(capability_name=tool_name, input_payload=tool_input)
    step_start = time.time()

    decision = gate.evaluate(call, context=context)
    if decision.action != "allow":
        return {
            "result": {
                "ok": False,
                "error": {
                    "code": decision.code or "POLICY_DENIED",
                    "message": decision.reason or "Blocked by policy gate",
                    "retryable": False,
                },
            },
            "elapsed_ms": int((time.time() - step_start) * 1000),
            "status": "error",
            "error_msg": decision.reason or decision.code,
        }

    registry = get_tool_registry()
    if not registry:
        return {
            "result": {"ok": False, "error": {"code": "REGISTRY_NOT_READY", "message": "ToolRegistry not initialized"}},
            "elapsed_ms": int((time.time() - step_start) * 1000),
            "status": "error",
            "error_msg": "ToolRegistry not initialized",
        }

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
            "error": {"code": "TOOL_TIMEOUT", "message": "tool invocation timeout", "retryable": True},
        }
    except Exception as exc:
        logger.exception("tool execution failed for tool=%s", tool_name)
        result = {
            "ok": False,
            "error": {
                "code": "TOOL_INVOKE_EXCEPTION",
                "message": f"tool invoke exception: {str(exc)[:200]}",
                "retryable": False,
            },
        }

    elapsed_ms = int((time.time() - step_start) * 1000)
    ok = bool(result.get("ok", False))
    status = "completed" if ok else "error"
    error_msg = _error_text(result.get("error")) if not ok else None
    return {"result": result, "elapsed_ms": elapsed_ms, "status": status, "error_msg": error_msg}


# ────────────────────────────────────────────────────────────────────────────
# _parallel_tool_execution：并行执行多个工具并合并结果
# ────────────────────────────────────────────────────────────────────────────
async def _parallel_tool_execution(state: State, actions: list[dict]) -> dict:
    """Execute all tools in ``actions`` concurrently and merge results."""
    # Guard: remaining iterations must cover parallel actions
    current_iteration = int(state.get("iteration_count", 0) or 0)
    remaining = MAX_ITERATIONS - current_iteration
    if len(actions) > remaining:
        logger.warning(
            "_parallel_tool_execution: %d parallel tools exceed remaining %d iterations; truncating to %d",
            len(actions), remaining, remaining,
        )
        actions = actions[:remaining]
        if not actions:
            result_str = json.dumps({
                "ok": False,
                "error": {"code": "ITERATION_BUDGET_EXCEEDED", "message": "No remaining iterations for parallel execution", "retryable": False},
            }, ensure_ascii=False)
            return {
                "tool_result": result_str,
                "tool_steps": state.get("tool_steps", []),
                "current_tool": None,
                "tool_input": None,
                "last_tool_name": None,
                "last_tool_query": None,
                "reasoning_steps": state.get("reasoning_steps", []),
                "route": "agent",
            }

    gate = _build_policy_gate()
    context = PolicyContext(
        conversation_id=str(state.get("conversation_id") or ""),
        agent_id=str(state.get("active_agent") or "agent.main"),
    )

    raw_results = await asyncio.gather(
        *[_execute_single_tool(
            str(a.get("tool", "")).strip().lower(),
            {"query": a.get("query", "")},
            gate,
            context,
        ) for a in actions],
        return_exceptions=True,
    )

    results = []
    new_steps = list(state.get("tool_steps", []))
    reasoning_msgs = []

    for i, action in enumerate(actions):
        raw = raw_results[i]
        if isinstance(raw, BaseException):
            result = {
                "ok": False,
                "error": {"code": "PARALLEL_EXCEPTION", "message": str(raw)[:200], "retryable": False},
            }
            elapsed_ms = 0
            status = "error"
            error_msg = str(raw)[:200]
        else:
            result = raw["result"]
            elapsed_ms = raw["elapsed_ms"]
            status = raw["status"]
            error_msg = raw.get("error_msg")

        results.append(result)

        tool_name = str(action.get("tool", "")).strip().lower()
        step_record = normalize_tool_step_record(
            tool_name=tool_name,
            tool_input=action,
            status=status,
            elapsed_ms=elapsed_ms,
            timestamp=time.time(),
            error=error_msg,
        )
        new_steps.append(step_record)

        if status == "completed":
            reasoning_msgs.append(f"[tool_node] Tool '{tool_name}' executed successfully.")
        else:
            reasoning_msgs.append(f"[tool_node] Tool '{tool_name}' returned error: {error_msg}")

    merged = {"parallel": True, "results": results}
    result_str = json.dumps(merged, ensure_ascii=False)

    return {
        "tool_result": result_str,
        "tool_steps": new_steps,
        "current_tool": None,
        "tool_input": None,
        "last_tool_name": None,
        "last_tool_query": None,
        "reasoning_steps": state.get("reasoning_steps", []) + reasoning_msgs,
        "route": "agent",
    }


# ────────────────────────────────────────────────────────────────────────────
# tool_node：工具执行节点
# ────────────────────────────────────────────────────────────────────────────
async def tool_node(state: State) -> dict:
    tool_input = state.get("tool_input") or {}
    tool_name = state.get("current_tool") or ""
    logging.info("[TOOL_NODE] 🛠️ executing tool=%s input_keys=%s", tool_name, list(tool_input.keys())[:5])

    # ── Parallel execution path ──
    if "actions" in tool_input:
        return await _parallel_tool_execution(state, tool_input["actions"])

    # ── Single-tool execution path (unchanged) ──
    tool_name = state.get("current_tool") or ""
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
            result = {"ok": False, "error": {"code": "REGISTRY_NOT_READY", "message": "ToolRegistry not initialized"}}
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

    logging.info("[TOOL_NODE] %s tool=%s elapsed=%dms status=%s",
                 "✅" if status == "completed" else "❌",
                 tool_name, int(elapsed_time * 1000), status)

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

[Output Instructions]
- NEVER output raw Python/matplotlib code blocks — they were already executed
- NEVER output localhost image URLs — images are auto-uploaded to cloud storage
- Only describe the analysis results and what the charts show
- Keep answers concise and well-structured
- Reply in the same language as the user's question

Current time: {now_str}
"""


async def answer_node(state: State) -> dict:
    """Phase 3: Generate streaming final answer with [CHART:n] markers."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    system_content = _ANSWER_SYSTEM_PROMPT_TEMPLATE.format(
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
            "route": "end",
        }

    return {
        "messages": [response],
        "route": "end",
    }


# ────────────────────────────────────────────────────────────────────────────
# Plan-Execute-Compose: planning_node (Phase 1 — JSON Mode)
# ────────────────────────────────────────────────────────────────────────────

def _validate_plan_json(plan: dict) -> tuple[bool, str]:
    """Validate execution plan JSON schema.

    Required top-level keys: title (str), steps (list)
    Each step requires: step_id (int), description (str), required_tools (list)
    Optional per step: expected_artifacts (list of {type, purpose, chart_type})
    """
    if not isinstance(plan, dict):
        return False, "Plan must be a JSON object"
    # Auto-fix missing title
    if "title" not in plan or not isinstance(plan["title"], str):
        plan["title"] = "Research Report"
    if "steps" not in plan or not isinstance(plan["steps"], list):
        return False, "Plan must have a 'steps' array field"
    if len(plan["steps"]) == 0:
        return False, "Plan must have at least one step"
    for i, step in enumerate(plan["steps"]):
        if not isinstance(step, dict):
            return False, f"Step {i} must be a JSON object"
        # Auto-fix missing step_id
        if "step_id" not in step:
            step["step_id"] = i + 1
        if "description" not in step or not isinstance(step["description"], str):
            return False, f"Step {i} missing 'description' string"
        if "required_tools" not in step or not isinstance(step["required_tools"], list):
            return False, f"Step {i} missing 'required_tools' list"
    return True, ""


_PLANNING_SYSTEM_PROMPT = """\
You are a research planner. Given a user query, generate an execution plan as a JSON object.

For exploration, you have read-only tools: search, browser, time.
For chart/image generation, plan steps with required_tools: ["execute_python"]

Output ONLY a valid JSON object. No markdown wrapping, no explanation.

{
  "title": "Brief plan title",
  "steps": [
    {
      "step_id": 1,
      "description": "Step description — for search steps, write a specific search query. For chart steps, describe what chart to generate and what data to use.",
      "required_tools": ["search"],
      "expected_artifacts": [
        {"type": "data", "purpose": "What data this step produces", "chart_type": null}
      ]
    }
  ]
}

Rules:
- Each step must accomplish ONE unit of research or chart generation
- required_tools for SEARCH/data steps: ["search"] or ["browser"]
- required_tools for CHART steps: ["execute_python"] — system will auto-generate matplotlib code
- Chart step description MUST include: what chart to make (line/bar/pie/...), what data to visualize, axis labels
- expected_artifacts.chart_type: null | "line" | "bar" | "pie" | "scatter" | "area" | "radar"
- Only use "chart_type" when required_tools includes "execute_python"
- Limit to 7 steps maximum
- For simple questions (1 search is enough), output a single step
- CRITICAL: The "title" field is MANDATORY — always include it

To use a tool during planning, output: {"action":"tool","tool":"<tool_name>","query":"<search query>"}
When you have enough information for a plan, output the plan JSON directly. You MUST include both "title" (string) and "steps" (array) fields.
"""


def _build_planning_system_prompt(now_str: str, tool_descriptions: str) -> str:
    lines = [_PLANNING_SYSTEM_PROMPT]
    if now_str:
        lines.append(f"\nCurrent time: {now_str}")
    if tool_descriptions:
        lines.append(f"\nAvailable tools:\n{tool_descriptions}")
    return "\n".join(lines)


_GREETING_PATTERNS = re.compile(
    r"(hello|hi|hey|good morning|good afternoon|good evening|how are you|nice to meet you|thanks|thank you|bye|goodbye)",
    re.IGNORECASE,
)


def _is_trivial_query(text: str) -> bool:
    """Detect trivial queries that don't need planning: short text or exact greetings."""
    stripped = text.strip()
    if len(stripped) < 8:
        return True
    if _GREETING_PATTERNS.fullmatch(stripped):
        return True
    return False


def _generate_fallback_plan(query: str) -> dict:
    """Generate a minimal single-step fallback plan."""
    return {
        "title": "Research: " + query[:60],
        "steps": [
            {
                "step_id": 1,
                "description": f"Search for information about: {query}",
                "required_tools": ["search"],
                "expected_artifacts": [
                    {"type": "data", "purpose": "Research results for the query", "chart_type": None}
                ],
            }
        ],
    }


# ────────────────────────────────────────────────────────────────────────────
# Chart code generation helper
# ────────────────────────────────────────────────────────────────────────────

_CHART_CODE_PROMPT = """\
You are a Python matplotlib expert. Generate Python code to create ONE chart based on the specification.

Specification:
{spec}

Available data context (from previous research steps):
{data_context}

CRITICAL RULES — follow exactly:
1. Start with: import matplotlib.pyplot as plt; import numpy as np
2. The following are pre-imported in the execution context — use them directly:
   cn_font (FontProperties), Palette, ChartSpec, SeriesSpec, SliceSpec, PointSpec, MatplotlibRenderer
4. ALL text elements MUST use `fontproperties=cn_font` — example: ax.set_title("标题", fontproperties=cn_font)
5. Get colors from Palette: Palette.get_series_colors(N) — returns PaletteColor objects with .hex and .name_cn
6. Set figure size to (12, 6)
7. Include title, axis labels, legend if applicable
8. Build a ChartSpec and call MatplotlibRenderer().render_from_spec() to render:
   colors = Palette.get_series_colors(len(series_data))
   spec = ChartSpec(
       title="图表标题",
       chart_type="bar",  # or "line"/"pie"/"scatter"/"histogram"/"heatmap"
       xlabel="X轴标签",
       ylabel="Y轴标签",
       labels=["2020", "2021", "2022", "2023", "2024"],
       series=[SeriesSpec(name="系列名", color=colors[i].hex, color_name=colors[i].name_cn, values=[10, 20, 30])],
   )
   renderer = MatplotlibRenderer()
   result = renderer.render_from_spec(spec, "chart_0.png")
   For pie charts: slices=[SliceSpec(label="A", value=30, color=colors[0].hex, color_name=colors[0].name_cn)]
   For scatter charts: points=[PointSpec(x=1, y=2, label="pt1")]
9. Output ONLY valid Python code — no markdown wrappers, no explanation
10. Do NOT call plt.savefig() or plt.show() directly — render_from_spec() handles saving
11. PROHIBITED: Do NOT use plt.rcParams['font.sans-serif'] — font is handled via fontproperties=cn_font
"""


async def _generate_chart_code(
    step_description: str,
    expected_artifacts: list[dict],
    previous_results: list[dict],
) -> str:
    """Generate matplotlib Python code for a chart step using a small LLM call."""
    # Build data context from previous results
    data_lines = []
    for i, r in enumerate(previous_results):
        status = r.get("status", "?")
        step_id = r.get("step_id", i)
        tool_data = r.get("data", [])
        for td in tool_data:
            tool_name = td.get("tool", "?")
            tool_status = td.get("status", "?")
            data_lines.append(f"[Step {step_id}] {tool_name}: {tool_status}")

    data_context = "\n".join(data_lines) if data_lines else "No previous data available — use reasonable sample data."

    # Build chart spec from expected_artifacts
    spec_lines = [f"Description: {step_description}"]
    for ea in expected_artifacts:
        chart_type = ea.get("chart_type", "line")
        purpose = ea.get("purpose", "")
        spec_lines.append(f"Chart type: {chart_type}")
        spec_lines.append(f"Purpose: {purpose}")
    spec = "\n".join(spec_lines)

    prompt = _CHART_CODE_PROMPT.format(spec=spec, data_context=data_context)

    llm = _build_llm(streaming=False, json_mode=False)
    llm.temperature = 0.1

    try:
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        content = str(response.content or "").strip()
        # Strip markdown wrappers if present
        if content.startswith("```python"):
            content = content[9:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()
    except Exception:
        # Fallback: generate minimal chart code
        chart_type = expected_artifacts[0].get("chart_type", "line") if expected_artifacts else "line"
        title = expected_artifacts[0].get("purpose", step_description) if expected_artifacts else step_description
        return f'''import matplotlib.pyplot as plt
        import numpy as np
        from chart.font_manager import FontManager
        from chart.palette import Palette
        from chart.chart_spec import ChartSpec, SeriesSpec
        from chart.renderers.matplotlib_renderer import MatplotlibRenderer

        cn_font = FontManager.get_cn_font()
        x = np.arange(10)
        y = np.random.randn(10).cumsum()

        spec = ChartSpec(
            title="{title}",
            chart_type="{chart_type}",
            xlabel="X",
            ylabel="Y",
            series=[SeriesSpec(name="Data", color=Palette.PRIMARY.hex, color_name=Palette.PRIMARY.name_cn, values=y.tolist())],
        )
        renderer = MatplotlibRenderer()
        result = renderer.render_from_spec(spec, "chart_0.png")
        print(f"Chart saved: {{result.image_path}}")
        print(f"Summary: {{result.summary}}")'''


# ────────────────────────────────────────────────────────────────────────────
# Artifact dedup helpers
# ────────────────────────────────────────────────────────────────────────────


def _tokenize_purpose(text: str) -> list[str]:
    """Extract keywords from purpose text: Chinese bigram + English lowercase words.

    For CJK text: extracts all bigrams (sliding window of 2 chars) plus the full segment.
    For English text: extracts lowercase words.
    """
    if not text:
        return []
    # Extract CJK character sequences
    cjk = re.findall(r'[一-鿿]+', text)
    tokens = []
    for segment in cjk:
        for i in range(len(segment) - 1):
            tokens.append(segment[i:i + 2])
        if segment:
            tokens.append(segment)  # full segment too
    # Extract English words
    en_words = re.findall(r'[a-zA-Z]+', text.lower())
    tokens.extend(en_words)
    return tokens


def _check_artifact_dedup(candidate: dict, existing: list[dict]) -> dict | None:
    """Check if a candidate artifact already exists via Jaccard similarity on purpose keywords.

    Returns the matching existing artifact dict if similarity > 0.5, else None.
    Only compares artifacts of the same type.
    """
    c_type = candidate.get("type", "")
    c_keywords = set(_tokenize_purpose(candidate.get("purpose", "")))

    for artifact in existing:
        if artifact.get("type") != c_type:
            continue
        a_keywords = set(_tokenize_purpose(artifact.get("purpose", "")))
        if not c_keywords or not a_keywords:
            continue
        intersection = c_keywords & a_keywords
        union = c_keywords | a_keywords
        jaccard = len(intersection) / len(union)
        if jaccard > 0.5:
            return artifact  # match found

    return None  # no match


def _register_artifact(state, artifact_type: str, purpose: str, step_id: int, content_ref: str) -> str:
    """Register a new artifact in state and return its artifact_id."""
    existing = state.get("artifacts", [])
    artifact_id = f"{artifact_type}_{len(existing)}"
    entry = {
        "artifact_id": artifact_id,
        "type": artifact_type,
        "purpose": purpose,
        "source_step_id": step_id,
        "content_ref": content_ref,
    }
    existing.append(entry)
    return artifact_id


async def planning_node(state: State) -> dict:
    """Phase 1: Generate execution plan using JSON Mode LLM with read-only tools.

    Flow:
    1. Check fast path: trivial/greeting query -> empty plan -> route to composer
    2. Mini ReAct loop (max 3 rounds) with read-only tools
    3. Validate plan JSON schema
    4. On failure: retry once with error feedback -> fallback plan
    5. Set plan_phase to "executing" (or "composing" if empty)
    """
    logger.info("[PLANNING] ===== NODE START =====")

    # Extract user query
    user_query = ""
    for msg in reversed(list(state.get("messages", []))):
        if hasattr(msg, "type") and msg.type == "human":
            user_query = (msg.content or "").strip()
            break

    logger.info("[PLANNING] query='%s'", user_query[:100])

    # Fast path: trivial query
    if _is_trivial_query(user_query):
        logger.info("[PLANNING] trivial query detected — skipping planning, routing to composer")
        return {
            "execution_plan": None,
            "plan_phase": "composing",
            "reasoning_steps": _append_reason(state, _reason_record(
                "planning_node", "FAST_PATH",
                "Trivial query detected; skipping planning phase.",
            )),
        }

    # Build system prompt with read-only tools
    registry = get_tool_registry()
    tool_descriptions = ""
    if registry:
        tool_lines = []
        for t in registry.list_tools():
            name = str(t.get("name", "")).strip().lower()
            if name in ("search", "browser", "time", "execute_python"):
                tool_lines.append(f"  - {t['name']}: {t['description']}")
        tool_descriptions = "\n".join(tool_lines)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    system_prompt = _build_planning_system_prompt(now_str, tool_descriptions)

    # Mini ReAct loop (max 3 rounds)
    llm = _build_llm(streaming=False, json_mode=True)
    plan = None
    max_planning_rounds = 3

    pending_messages: list = []

    for planning_round in range(max_planning_rounds):
        msg_list = [SystemMessage(content=system_prompt)] + list(state["messages"]) + pending_messages

        # If we have tool observations from previous round, inject them
        if plan is None and planning_round > 0:
            # Add instruction to read state and produce plan
            msg_list.append(SystemMessage(content=(
                "Based on the information gathered, now produce the execution plan JSON. "
                "Make sure to include all steps with required_tools and expected_artifacts."
            )))

        try:
            response = await llm.ainvoke(msg_list)
            content = (response.content or "").strip()
            parsed = json.loads(content)

            # Check if LLM wants to call a tool (planning_round < max-1)
            action = str(parsed.get("action", "")).strip().lower()
            if action == "tool" and planning_round < max_planning_rounds - 1:
                tool_name = str(parsed.get("tool", "")).strip().lower()
                if tool_name in ("search", "browser", "time"):
                    query = str(parsed.get("query", "")).strip()
                    gate = _build_policy_gate()
                    context = PolicyContext(
                        conversation_id=str(state.get("conversation_id") or ""),
                        agent_id="planning",
                    )
                    tool_result = await _execute_single_tool(tool_name, {"query": query}, gate, context)
                    # Store observation in pending messages for next round
                    pending_messages.append(AIMessage(
                        content=json.dumps({
                            "action": "tool_result",
                            "tool": tool_name,
                            "result": tool_result.get("result", {}),
                        }, ensure_ascii=False)
                    ))
                    continue

            # Check if the response IS a plan (has title and steps)
            if "title" in parsed and "steps" in parsed:
                plan = parsed
                break
            else:
                # Response is something else — treat as plan_ready
                if "execution_plan" in parsed:
                    plan = parsed["execution_plan"]
                    break
                plan = parsed
                break

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("[PLANNING] JSON parse error (round %d): %s", planning_round, e)
            if planning_round < max_planning_rounds - 1:
                pending_messages.append(AIMessage(
                    content=f"JSON parse error. Output ONLY valid JSON with title and steps fields."
                ))
                continue
            plan = None

    # Validate plan
    if plan:
        is_valid, error_msg = _validate_plan_json(plan)
        if not is_valid:
            logger.warning("[PLANNING] plan validation failed: %s", error_msg)
            # Retry once with error feedback
            try:
                pending_messages.append(SystemMessage(
                    content=f"Plan validation error: {error_msg}. Please fix and output a valid plan JSON."
                ))
                msg_list = [SystemMessage(content=system_prompt)] + list(state["messages"]) + pending_messages
                response = await llm.ainvoke(msg_list)
                content = (response.content or "").strip()
                plan = json.loads(content)
                is_valid, error_msg = _validate_plan_json(plan)
                if not is_valid:
                    plan = None
            except (json.JSONDecodeError, TypeError):
                plan = None

    # Fallback: if still no valid plan, generate minimal plan
    if not plan:
        logger.info("[PLANNING] generating fallback plan for query: %s", user_query[:60])
        plan = _generate_fallback_plan(user_query)

    plan_phase = "composing" if not plan.get("steps") else "executing"

    return {
        "execution_plan": plan,
        "plan_phase": plan_phase,
        "messages": pending_messages,
        "reasoning_steps": _append_reason(state, _reason_record(
            "planning_node", "PLAN_READY",
            f"Generated plan: '{plan.get('title', '')}' with {len(plan.get('steps', []))} step(s)",
            extra={"step_count": len(plan.get("steps", []))},
        )),
    }


# ────────────────────────────────────────────────────────────────────────────
# execution_node: Phase 2 — Execute one step from the execution plan
# ────────────────────────────────────────────────────────────────────────────


async def execution_node(state: State, event_bus=None) -> dict:
    """Phase 2: Execute one step from the execution plan.

    For each step:
    1. Check artifact dedup for each expected_artifact
    2. For each required_tool, call _execute_single_tool (matched artifacts are referenced, not regenerated)
    3. Register new artifacts
    4. Store step result in execution_results
    5. Increment current_plan_step
    6. Set plan_phase to "composing" if all steps done

    Self-loop is controlled by conditional edges in multi_agent_graph.py.
    """
    plan = state.get("execution_plan")
    step_idx = state.get("current_plan_step", 0)

    logger.info("[EXECUTION] ===== NODE START: step_idx=%d, plan_has_steps=%s, artifacts_count=%d =====",
                step_idx, bool(plan and plan.get("steps")), len(state.get("artifacts", [])))

    if not plan or not plan.get("steps"):
        logger.info("[EXECUTION] no plan or empty steps → routing to composer")
        return {"plan_phase": "composing"}

    steps = plan["steps"]
    if step_idx >= len(steps):
        logger.info("[EXECUTION] step_idx(%d) >= len(steps)(%d) → routing to composer", step_idx, len(steps))
        return {"plan_phase": "composing"}

    step = steps[step_idx]
    step_id = int(step.get("step_id", step_idx))
    required_tools = step.get("required_tools", [])
    expected_artifacts = step.get("expected_artifacts", [])

    logger.info("[EXECUTION] executing step %d/%d: %s", step_idx + 1, len(steps), step.get("description", "")[:80])

    user_query = ""
    for msg in reversed(list(state.get("messages", []))):
        if hasattr(msg, "type") and msg.type == "human":
            user_query = (msg.content or "").strip()
            break

    accumulated_reasons = []
    existing_artifacts = list(state.get("artifacts", []))

    # Artifact dedup: for each expected artifact, check if it already exists
    artifact_ids = []
    for ea in expected_artifacts:
        match = _check_artifact_dedup(ea, existing_artifacts)
        if match:
            logger.info("[EXECUTION] artifact dedup match: type=%s purpose='%s' -> existing artifact %s",
                        ea.get("type"), ea.get("purpose", "")[:40], match.get("artifact_id"))
            artifact_ids.append(match.get("artifact_id"))
            accumulated_reasons.append(_reason_record(
                "execution_node", "ARTIFACT_DEDUP_MATCH",
                f"Artifact dedup match: type={ea.get('type')}, matched existing {match.get('artifact_id')}",
                extra={"candidate_type": ea.get("type"), "matched_id": match.get("artifact_id")},
            ))
        else:
            accumulated_reasons.append(_reason_record(
                "execution_node", "ARTIFACT_DEDUP_MISS",
                f"No dedup match for artifact type={ea.get('type')}, purpose='{ea.get('purpose', '')[:40]}'",
            ))

    # Execute tools for this step
    gate = _build_policy_gate()
    context = PolicyContext(
        conversation_id=str(state.get("conversation_id") or ""),
        agent_id=str(state.get("active_agent", "execution")),
    )

    tool_results = []
    step_status = "completed"

    import time as _time
    previous_results = list(state.get("execution_results", []))

    for tool_name in required_tools:
        tool_call_id = f"{tool_name}_{step_id}_{int(_time.time()*1000)}"

        # ── execute_python: generate chart code, execute, capture image URLs ──
        if tool_name == "execute_python":
            logger.info("[EXECUTION] generating chart code for step %d", step_id)
            if event_bus:
                event_bus.emit("tool.started", tool_call_id=tool_call_id, tool=tool_name,
                               arguments={"chart_type": expected_artifacts[0].get("chart_type", "line") if expected_artifacts else "line"})
            try:
                chart_code = await _generate_chart_code(
                    step.get("description", ""),
                    expected_artifacts,
                    previous_results,
                )
                logger.info("[EXECUTION] chart code generated (%d chars)", len(chart_code))
                result = await _execute_single_tool(tool_name, {"code": chart_code}, gate, context)
            except Exception as exc:
                logger.exception("[EXECUTION] chart generation failed for step %d", step_id)
                result = {"ok": False, "error": {"code": "CHART_GENERATION_FAILED", "message": str(exc)[:200], "retryable": False}, "elapsed_ms": 0, "status": "error", "error_msg": str(exc)[:200]}

            tool_results.append({"tool": tool_name, "status": result.get("status", "error"), "elapsed_ms": result.get("elapsed_ms", 0)})

            if result.get("status") == "completed":
                # Extract image URLs from execute_python result
                # result structure: {"result": {"ok": True, "data": {"output": "...", "images": {...}}}}
                outer_result = result.get("result", {})
                if isinstance(outer_result, dict):
                    data = outer_result.get("data", {})
                    images = data.get("images", {}) if isinstance(data, dict) else {}
                else:
                    images = {}
                if images:
                    for fname, url in images.items():
                        artifact_id = _register_artifact(state, artifact_type="image", purpose=f"Chart: {step.get('description', '')[:60]}", step_id=step_id, content_ref=url)
                        artifact_ids.append(artifact_id)
                        logger.info("[EXECUTION] registered chart artifact: %s -> %s", artifact_id, url)
                else:
                    logger.warning("[EXECUTION] chart generated but no images found in result")
                if event_bus:
                    event_bus.emit("tool.finished", tool_call_id=tool_call_id, tool=tool_name, result={"status": "completed", "images": len(images)})
            else:
                step_status = "error"
                if event_bus:
                    event_bus.emit("tool.failed", tool_call_id=tool_call_id, tool=tool_name, error=str(result.get("error_msg", "chart generation failed")))
            continue

        # ── Normal tools (search, browser, time, etc.) ──
        search_query = step.get("description", user_query)
        logger.info("[EXECUTION] invoking tool: %s query='%s'", tool_name, search_query[:80])
        if event_bus:
            event_bus.emit("tool.started", tool_call_id=tool_call_id, tool=tool_name, arguments={"query": search_query})

        try:
            result = await _execute_single_tool(tool_name, {"query": search_query}, gate, context)
        except Exception as exc:
            logger.exception("[EXECUTION] tool '%s' failed", tool_name)
            result = {"ok": False, "error": {"code": "TOOL_INVOKE_EXCEPTION", "message": str(exc)[:200], "retryable": False}, "elapsed_ms": 0, "status": "error", "error_msg": str(exc)[:200]}

        tool_results.append({"tool": tool_name, "status": result.get("status", "error"), "elapsed_ms": result.get("elapsed_ms", 0)})

        if result.get("status") == "error":
            error_info = result.get("error", {})
            is_retryable = error_info.get("retryable", True) if isinstance(error_info, dict) else True
            if not is_retryable:
                logger.info("[EXECUTION] skipping retry for tool: %s (non-retryable error)", tool_name)
                step_status = "error"
                if event_bus:
                    event_bus.emit("tool.failed", tool_call_id=tool_call_id, tool=tool_name, error=str(error_info.get("message", error_info.get("code", "unknown error"))))
            else:
                logger.info("[EXECUTION] retrying tool: %s (first attempt failed)", tool_name)
                result = await _execute_single_tool(tool_name, {"query": search_query}, gate, context)
                tool_results[-1] = {"tool": tool_name, "status": result.get("status", "error"), "elapsed_ms": result.get("elapsed_ms", 0) + tool_results[-1].get("elapsed_ms", 0)}

        if result.get("status") == "error":
            step_status = "error"
            if event_bus:
                event_bus.emit("tool.failed", tool_call_id=tool_call_id, tool=tool_name, error=str(result.get("error_msg", "tool execution failed")))
        else:
            if event_bus:
                event_bus.emit("tool.finished", tool_call_id=tool_call_id, tool=tool_name, result={"status": "completed", "elapsed_ms": result.get("elapsed_ms", 0)})

        # Register search/data results as artifact
        if result.get("status") == "completed" and result.get("result"):
            content_ref = f"tool:{tool_name}:{step_id}"
            artifact_id = _register_artifact(
                state, artifact_type=f"tool_result_{tool_name}",
                purpose=f"Result from {tool_name} for step {step_id}: {step.get('description', '')[:60]}",
                step_id=step_id, content_ref=content_ref,
            )
            artifact_ids.append(artifact_id)

    # Build step result
    step_result = {
        "step_id": step_id,
        "status": step_status,
        "data": tool_results,
        "artifacts": artifact_ids,
    }

    existing_results = list(state.get("execution_results", []))
    existing_results.append(step_result)

    next_step_idx = step_idx + 1
    new_plan_phase = "composing" if next_step_idx >= len(steps) else "executing"

    return {
        "execution_results": existing_results,
        "artifacts": state.get("artifacts", []),
        "current_plan_step": next_step_idx,
        "plan_phase": new_plan_phase,
        "reasoning_steps": state.get("reasoning_steps", []) + accumulated_reasons + [_reason_record(
            "execution_node", "STEP_COMPLETED",
            f"Step {step_id}/{len(steps)} completed with status={step_status}",
            extra={"step_id": step_id, "status": step_status, "tool_count": len(required_tools)},
        )],
    }


# ────────────────────────────────────────────────────────────────────────────
# composer_node: Phase 3 — Generate structured final report from plan + results
# ────────────────────────────────────────────────────────────────────────────


def _build_composer_system_prompt(
    plan: dict | None,
    results: list[dict],
    artifacts: list[dict],
    now_str: str,
) -> str:
    """Build the system prompt for the composer LLM, including plan, results, and artifacts."""
    plan_section = json.dumps(plan, ensure_ascii=False, indent=2) if plan else "No plan was generated (direct response)."

    results_section = (
        json.dumps(results, ensure_ascii=False, indent=2)
        if results
        else "No research results available."
    )

    def _format_artifacts(artifacts_list: list[dict]) -> str:
        if not artifacts_list:
            return "No visual artifacts available."
        lines = ["Available Visual Assets:"]
        for a in artifacts_list:
            aid = a.get("artifact_id", "?")
            atype = a.get("type", "?")
            purpose = a.get("purpose", "")
            content_ref = a.get("content_ref", "")
            if atype == "image" and content_ref:
                # For images, provide the actual URL and markdown syntax hint
                meta_hint = ""
                if "metadata" in a and a["metadata"]:
                    series_info = a["metadata"].get("series", [])
                    summary = a.get("summary", "")
                    if series_info:
                        colors_str = "; ".join(
                            f'{s.get("name","")}（{s.get("color_name","")}）'
                            for s in series_info
                        )
                        meta_hint = f" [colors: {colors_str}]"
                    if summary:
                        meta_hint += f" [summary: {summary}]"
                lines.append(
                    f"- [{aid}] IMAGE for '{purpose}' — use this Markdown: "
                    f"![{purpose}]({content_ref}){meta_hint}"
                )
            else:
                lines.append(f"- [{aid}] type={atype}, purpose='{purpose}', ref={content_ref}")
        return "\n".join(lines)

    artifacts_section = _format_artifacts(artifacts)

    return f"""\
You are a professional data analyst. Generate a structured report based on the research results.

[Execution Plan]
{plan_section}

[Research Results]
{results_section}

[Available Visual Assets]
{artifacts_section}

[Instructions]
- Write a professional analysis report
- Only reference visual assets from the [Available Visual Assets] list above
- Use Markdown image syntax ONLY for artifacts listed above: ![description](artifact_ref)
- CRITICAL: Do NOT reference or embed images from external websites (no unsplash.com, no wikimedia, no third-party URLs)
- CRITICAL: Do NOT use any image URL that contains "http://" or "https://" unless it is an artifact ref from the list above
- If there are no applicable visual assets, do NOT invent or reference any images — write text-only
- Interleave text with available images naturally: introduction -> [IMAGE] -> analysis -> [IMAGE] -> conclusion
- Do NOT output code blocks, localhost URLs, or raw tool output
- Reply in the same language as the user's question
- Structure: title, executive summary, sections per plan step, conclusion
- If no research data was collected, just answer the user's question directly and conversationally

[Chart Color Rules]
- CRITICAL: All chart color/数值 descriptions MUST come from chart metadata's series color_name and summary, NOT from image inspection
- When referencing chart series, use format: "系列名（颜色名）" — e.g., "GDP（蓝色）"
- The chart summary field contains programmatically extracted statistics (max/min/avg/trend) — use these when describing data
- Charts WITHOUT metadata (no series/summary) must NOT have color or numeric descriptions — describe only the chart type and title

Current time: {now_str}
"""


async def composer_node(state: State) -> dict:
    """Phase 3: Generate structured report from plan + results + artifacts.

    Builds a system prompt with:
    - The execution plan
    - Research results per step
    - Available visual artifacts (charts)

    Uses Normal Mode (streaming) LLM with no tool binding.
    Output is streamed via astream_events -> SSE as message.delta.
    """
    plan = state.get("execution_plan")
    results = state.get("execution_results", [])
    artifacts = state.get("artifacts", [])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    logger.info("[COMPOSER] ===== NODE START: plan=%s, results_count=%d, artifacts_count=%d =====",
                bool(plan), len(results), len(artifacts))
    logger.info("[COMPOSER] building report from %d result step(s)", len(results))

    system_prompt = _build_composer_system_prompt(plan, results, artifacts, now_str)

    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])

    llm = _build_llm(streaming=True, json_mode=False)

    try:
        response = await llm.ainvoke(messages)
    except Exception as exc:
        logger.exception("composer_node: LLM invoke failed")
        fallback = "Sorry, an error occurred while generating the answer. Please try again."
        return {
            "messages": [AIMessage(content=fallback)],
            "plan_phase": "done",
        }

    return {
        "messages": [response],
        "plan_phase": "done",
    }
