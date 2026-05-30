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
You are a ReAct agent. Follow this internal cycle:

  [Thought] → [Action] → [Observation] → (repeat) → [Final Answer]

CRITICAL RULES:
1. Your Thought/Reasoning is INTERNAL ONLY — NEVER output it as text
2. Your response must be EXACTLY ONE of:
   a) A tool-call JSON: {"action": "tool", "tool": "<name>", "query": "<query>"}
   b) A Final Answer in natural language (the user's language)
3. NEVER output both — each response is either JSON OR Final Answer, never both

Tool chaining:
- After search results → OPEN at least one result with browser for full details
- After reading a page → if info is enough, give Final Answer; if not, refine and search again
- **IMPORTANT**: Call `generate_chart` tool IMMEDIATELY when you have numerical data — do NOT wait until the end. Generate charts inline as you analyze. Continue analysis AFTER the chart.

When to give Final Answer:
- You have enough information to answer the user comprehensively
- Include ALL relevant data, numbers, and analysis
- Call `generate_chart` BEFORE giving the Final Answer if the user asked for charts

Do NOT:
- Output [Thought] tags or any thinking/reasoning text (keep ALL thoughts internal)
- Output JSON and text in the same response — each response is JSON-only OR text-only
- Call the same tool with the same query twice
- Give up early — keep going until you have enough info
- If you cannot find enough data after searching, provide a brief Final Answer stating so
- Your response must NEVER contain [Thought], [Action], or [Observation] tags\
"""

# Legacy hint — kept for backward compat, merged into _REACT_SYSTEM_PROMPT
_TOOL_FORMAT_HINT = _REACT_SYSTEM_PROMPT

# Maximum number of tool calls in one turn — configurable via MAX_TOOL_ITERATIONS env var
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


def _build_llm(streaming: bool = True) -> ChatOpenAI:
    """创建并返回 ChatOpenAI 实例（集中在一处，方便统一修改参数）。"""
    return ChatOpenAI(
        model=settings.model,
        temperature=settings.temperature,
        streaming=streaming,
        api_key=settings.api_key,
        base_url=settings.base_url,
        extra_body={
            "thinking": {"type": "disabled"},
        }
    )


def _parse_tool_call(content: str) -> tuple[str, str] | None:
    """Find and parse model tool intent JSON — anywhere in the response.

    LLMs sometimes emit a preamble before the JSON, so we search for the
    first JSON object that contains the expected tool-call fields.
    """
    content = content.strip()

    # Fast path: whole response is JSON
    if content.startswith("{"):
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            result = _extract_tool_from_parsed(parsed)
            if result is not None:
                return result

    # Slow path: search for JSON blocks embedded in preamble text
    depth = 0
    start = -1
    for i, ch in enumerate(content):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = content[start:i + 1]
                try:
                    parsed = json.loads(candidate)
                except (json.JSONDecodeError, TypeError):
                    start = -1
                    continue
                if isinstance(parsed, dict):
                    result = _extract_tool_from_parsed(parsed)
                    if result is not None:
                        return result
                start = -1

    return None


def _extract_tool_from_parsed(parsed: dict) -> tuple[str, str] | None:
    action = str(parsed.get("action", "")).strip()
    query = str(parsed.get("query", "")).strip()

    if action == "tool":
        tool_name = str(parsed.get("tool", "")).strip()
    else:
        tool_name = action

    if not tool_name:
        return None
    return tool_name, query


def _extract_iso_date(text: str) -> str | None:
    m = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    return m.group(0) if m else None


def _strip_thought_tags(text: str) -> str:
    """Remove [Thought]...[/Thought] and standalone [Thought] tags from LLM output."""
    # Remove [Thought]...[/Thought] blocks
    text = re.sub(r"\[Thought\][\s\S]*?\[/Thought\]", "", text)
    # Remove lines that start with [Thought] (some models use single-line format)
    text = re.sub(r"^\[Thought\].*$", "", text, flags=re.MULTILINE)
    # Remove isolated [Thought] and [/Thought] tags
    text = text.replace("[Thought]", "").replace("[/Thought]", "")
    return text.strip()


def _latest_user_text(state: State) -> str:
    raw_messages = list(state.get("messages") or [])
    for msg in reversed(raw_messages):
        msg_type = getattr(msg, "type", None)
        msg_content = getattr(msg, "content", None)
        if msg_type == "human" and isinstance(msg_content, str):
            return msg_content.strip()
        if isinstance(msg, dict):
            role = msg.get("role") or msg.get("type")
            content = msg.get("content")
            if role in {"user", "human"} and isinstance(content, str):
                return content.strip()
    return ""


async def _generate_forced_final_answer(
    llm: ChatOpenAI,
    state: State,
    now_str: str,
    tool_result_sanitized: str,
) -> str:
    guidance = [
        "You are a helpful AI assistant.",
        f"Current date and time (server): {now_str}",
        "You already have enough tool evidence.",
        "Now provide a concise final answer based ONLY on the provided tool result context.",
        "Do NOT call any tool.",
        "Do NOT output JSON.",
        "Reply in the same language as the user's original question.",
    ]
    if tool_result_sanitized:
        guidance.append(f"Tool result context (sanitized):\n{tool_result_sanitized}")
    forced_messages = [SystemMessage(content="\n".join(guidance))] + list(state["messages"])
    response = await llm.ainvoke(forced_messages)
    text = (response.content or "").strip()
    # If the LLM still outputs JSON despite instructions, discard and use fallback
    if text and (text.startswith("{") or text.startswith("```json")):
        logger.warning("_generate_forced_final_answer: LLM returned JSON, using local fallback")
        return _build_local_final_fallback(state.get("tool_result"))
    if text:
        return text
    return _build_local_final_fallback(state.get("tool_result"))


# ────────────────────────────────────────────────────────────────────────────
# agent_node：LLM 决策节点
# ────────────────────────────────────────────────────────────────────────────
async def agent_node(state: State) -> dict:
    registry = get_tool_registry()

    # 1. 构建工具列表描述
    tools_desc = ""
    if registry:
        for t in registry.list_tools():
            tools_desc += f"  - {t['name']}: {t['description']}\n"

    # 2. ReAct system prompt
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    system_lines = [
        _REACT_SYSTEM_PROMPT,
        f"Current server time: {now_str}",
    ]
    if tools_desc:
        system_lines.append(f"Available tools:\n{tools_desc}")

    # 3. Observation: feed tool result back with guidance to continue or finish
    tool_result = state.get("tool_result")
    tool_result_sanitized = normalize_tool_result_for_prompt(tool_result)
    current_iteration = int(state.get("iteration_count", 0) or 0)
    if tool_result_sanitized:
        remaining = MAX_ITERATIONS - current_iteration
        if remaining > 0:
            system_lines.append(
                f"\n--- Observation (iteration {current_iteration}/{MAX_ITERATIONS}) ---\n"
                f"{tool_result_sanitized}\n"
                "--- End Observation ---\n"
            )
            # ReAct guidance: push LLM to dig deeper before answering
            if "browser:" in tool_result_sanitized or "browser" in tool_result_sanitized.lower():
                system_lines.append(
                    "You just read a web page. If the content answers the user's question, "
                    "provide the Final Answer now. If key details are still missing, "
                    "search for more specific info or open another relevant page."
                )
            elif "result_count:" in tool_result_sanitized:
                system_lines.append(
                    "You have search results. Before answering, OPEN at least one promising "
                    "result with the browser tool to read the actual content. "
                    "Do NOT give the Final Answer based only on search snippets."
                )
            else:
                system_lines.append(
                    "Continue the ReAct cycle: if you need more info, call another tool. "
                    f"Otherwise, provide the Final Answer. ({remaining} iterations remaining)"
                )
        else:
            system_lines.append(
                f"\n--- Final Observation ---\n{tool_result_sanitized}\n"
                "No more tool calls allowed. Provide your Final Answer now."
            )

    system_prompt = "\n".join(system_lines)

    # 4. 调用 LLM
    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    llm = _build_llm()
    try:
        response = await llm.ainvoke(messages)
    except Exception as exc:
        logger.warning("agent_node ainvoke failed, fallback to local final answer: %s", exc)
        fallback = _build_local_final_fallback(tool_result)
        reason = _reason_record(
            node="agent_node",
            code="LLM_INVOKE_FAILED",
            message="LLM invoke failed; returned local fallback final answer.",
            extra={"error": str(exc)[:200]},
        )
        return {
            "messages": [AIMessage(content=fallback)],
            "current_tool": None,
            "tool_input": None,
            "last_guard_reason": reason,
            "consecutive_search_count": 0,
            "reasoning_steps": _append_reason(state, reason),
        }

    # 5. 尝试解析是否要调工具
    content = (response.content or "").strip()
    # Strip [Thought] tags that some models output despite prompt instructions
    content = _strip_thought_tags(content)
    try:
        parsed = _parse_tool_call(content)
        if parsed:
            tool_name, query = parsed
            normalized_query = _normalize_query(query)
            consecutive_search_count = int(state.get("consecutive_search_count", 0) or 0)
            next_consecutive_search_count = (
                consecutive_search_count + 1 if tool_name.lower() == "search" else 0
            )
            max_consecutive_search_calls = _max_consecutive_search_calls()

            if current_iteration >= MAX_ITERATIONS:
                fallback = "抱歉，已达到本轮工具调用上限。基于已获取的信息，我无法给出完整的最终回答，请重试或缩小问题范围。"
                reason = _reason_record(
                    node="agent_node",
                    code="MAX_ITERATIONS_REACHED",
                    message=(
                        f"Tool call limit reached ({MAX_ITERATIONS}); forced final answer generation."
                    ),
                )
                return {
                    "messages": [AIMessage(content=fallback)],
                    "current_tool": None,
                    "tool_input": None,
                    "last_guard_reason": reason,
                    "consecutive_search_count": 0,
                    "reasoning_steps": _append_reason(state, reason),
                }

            # 通用去重：同一轮里如果重复同一工具同一query，直接收敛
            last_tool_name = (state.get("last_tool_name") or "").strip().lower()
            last_tool_query = _normalize_query(str(state.get("last_tool_query") or ""))
            if last_tool_name == tool_name.lower() and last_tool_query == normalized_query:
                reason = _reason_record(
                    node="agent_node",
                    code="DUPLICATE_TOOL_CALL_BLOCKED",
                    message=f"Prevented duplicate tool call: tool='{tool_name}', query='{query}'.",
                    extra={"tool": tool_name, "query": query},
                )
                try:
                    forced = await _generate_forced_final_answer(
                        llm=llm,
                        state=state,
                        now_str=now_str,
                        tool_result_sanitized=tool_result_sanitized,
                    )
                except Exception as exc:
                    logger.warning("agent_node forced final answer failed, fallback to local answer: %s", exc)
                    forced = _build_local_final_fallback(tool_result)
                return {
                    "messages": [AIMessage(content=forced)],
                    "current_tool": None,
                    "tool_input": None,
                    "last_tool_name": None,
                    "last_tool_query": None,
                    "last_guard_reason": reason,
                    "consecutive_search_count": 0,
                    "reasoning_steps": _append_reason(state, reason),
                }

            # Guard: limit consecutive searches to prevent infinite loops,
            # but allow refined searches with different queries (duplicate check above handles exact repeats)
            if tool_name.lower() == "search" and next_consecutive_search_count > max_consecutive_search_calls:
                reason = _reason_record(
                    node="agent_node",
                    code="MAX_CONSECUTIVE_SEARCH_REACHED",
                    message="Consecutive search call limit reached; forced final answer.",
                    extra={
                        "count": next_consecutive_search_count,
                        "limit": max_consecutive_search_calls,
                    },
                )
                try:
                    forced = await _generate_forced_final_answer(
                        llm=llm,
                        state=state,
                        now_str=now_str,
                        tool_result_sanitized=tool_result_sanitized,
                    )
                except Exception as exc:
                    logger.warning("agent_node max-consecutive-search finalization failed: %s", exc)
                    forced = _build_local_final_fallback(tool_result)
                return {
                    "messages": [AIMessage(content=forced)],
                    "current_tool": None,
                    "tool_input": None,
                    "last_tool_name": None,
                    "last_tool_query": None,
                    "last_guard_reason": reason,
                    "consecutive_search_count": 0,
                    "reasoning_steps": _append_reason(state, reason),
                }

            # 避免在单轮里重复调用 time（常见卡死点）
            if tool_name == "time" and tool_result_sanitized.startswith("time:"):
                latest_user = _latest_user_text(state)
                latest_user_lower = latest_user.lower()
                needs_fresh_search = any(k in latest_user_lower for k in [
                    "新闻", "大新闻", "天气", "最新", "today", "latest", "recent", "now", "weather", "news"
                ])
                date_hint = _extract_iso_date(tool_result_sanitized) or now_str.split(" ")[0]

                if needs_fresh_search:
                    reason = _reason_record(
                        node="agent_node",
                        code="TIME_REPEAT_AUTOSWITCH_SEARCH",
                        message=f"Prevented repeated time tool call; auto-switched to search with date {date_hint}.",
                        extra={"date_hint": date_hint},
                    )
                    auto_query = f"{date_hint} {latest_user}".strip()
                    return {
                        "current_tool": "search",
                        "tool_input": {"query": auto_query},
                        "tool_result": None,
                        "iteration_count": current_iteration + 1,
                        "last_tool_name": "search",
                        "last_tool_query": auto_query,
                        "consecutive_search_count": consecutive_search_count + 1,
                        "reasoning_steps": _append_reason(state, reason),
                    }

                # 非时效检索场景：直接结束，避免无意义 time 循环
                reason = _reason_record(
                    node="agent_node",
                    code="TIME_REPEAT_FINALIZED",
                    message="Prevented repeated time tool call; returned final answer.",
                )
                return {
                    "messages": [AIMessage(content=f"当前时间已获取：{tool_result_sanitized.replace('time: ', '', 1)}")],
                    "current_tool": None,
                    "tool_input": None,
                    "last_tool_name": None,
                    "last_tool_query": None,
                    "last_guard_reason": reason,
                    "consecutive_search_count": 0,
                    "reasoning_steps": _append_reason(state, reason),
                }

            reason = _reason_record(
                node="agent_node",
                code="TOOL_CALL_DECIDED",
                message=f"Decided to call tool '{tool_name}' with query: '{query}'",
                extra={"tool": tool_name},
            )
            return {
                "current_tool": tool_name,
                "tool_input": {"query": query},
                "tool_result": None,
                "iteration_count": current_iteration + 1,
                "last_tool_name": tool_name,
                "last_tool_query": query,
                "consecutive_search_count": next_consecutive_search_count,
                "reasoning_steps": _append_reason(state, reason),
            }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass

    # 6. 普通文本回答
    reason = _reason_record(
        node="agent_node",
        code="DIRECT_ANSWER",
        message="Generated direct answer (no tool needed).",
    )
    return {
        "messages": [response],
        "current_tool": None,
        "tool_input": None,
        "last_tool_name": None,
        "last_tool_query": None,
        "last_guard_reason": reason,
        "consecutive_search_count": 0,
        "reasoning_steps": _append_reason(state, reason),
    }


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

    # If chart tool succeeded, emit chart spec immediately (inline rendering)
    pending_chart_spec = None
    extra = {}
    if tool_name == "generate_chart" and ok and isinstance(result, dict):
        data = result.get("data")
        if isinstance(data, dict) and data:
            pending_chart_spec = data
            extra["chart_specs"] = state.get("chart_specs", []) + [data]

    return {
        "tool_result": result_str,
        "tool_steps": new_tool_steps,
        "pending_chart_spec": pending_chart_spec,
        **extra,
        "current_tool": None,
        "tool_input": None,
        "reasoning_steps": state.get("reasoning_steps", []) + [step],
    }


# ────────────────────────────────────────────────────────────────────────────
# llm_node：V0.2 兼容节点
# ────────────────────────────────────────────────────────────────────────────
async def llm_node(state: State) -> dict:
    llm = _build_llm()
    response = await llm.ainvoke(state["messages"])
    return {"messages": [response]}


def _normalize_query(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _build_local_final_fallback(tool_result: str | None) -> str:
    safe_ctx = normalize_tool_result_for_prompt(tool_result)
    if not safe_ctx:
        return "抱歉，我已完成工具调用但暂时无法生成最终回答，请重试或换一个更具体的问题。"
    return "抱歉，我已收集到相关信息但无法生成完整总结。请重试一次，或缩小问题范围。"


def _build_observation_message(tool_name: str, result_str: str) -> str:
    """Build a ReAct Observation message from tool execution result.

    For browser results, includes the full page content (up to 4000 chars).
    For other tools, uses the normalized result.
    """
    try:
        parsed = json.loads(result_str)
    except Exception:
        sanitized = normalize_tool_result_for_prompt(result_str)
        return f"[Tool result: {tool_name}]\n{sanitized}" if sanitized else f"[Tool result: {tool_name}] completed."

    if isinstance(parsed, dict) and not parsed.get("ok", False):
        err = parsed.get("error", {})
        if isinstance(err, dict):
            return f"[Tool result: {tool_name}] ERROR - {err.get('message', str(err))}"
        return f"[Tool result: {tool_name}] ERROR - {err}"

    data = parsed.get("data")
    if isinstance(data, dict) and "url" in data and "text" in data:
        url = str(data.get("url", ""))[:120]
        title = str(data.get("title", "Untitled"))[:200]
        text = str(data.get("text", ""))
        length = int(data.get("length", len(text)))
        text_display = text[:4000]
        trunc_note = "\n[...truncated]" if len(text) > 4000 else ""
        return (
            f"[Tool result: {tool_name}]\n"
            f"URL: {url}\n"
            f"Title: {title}\n"
            f"Content ({length} chars):\n{text_display}{trunc_note}"
        )

    sanitized = normalize_tool_result_for_prompt(result_str)
    return f"[Tool result: {tool_name}]\n{sanitized}" if sanitized else f"[Tool result: {tool_name}] completed."


# ────────────────────────────────────────────────────────────────────────────
# chart_node：图表规划 + 生成 + 内容编排节点
# ────────────────────────────────────────────────────────────────────────────
async def chart_node(state: State) -> dict:
    """Analyze tool results, generate charts, and compose ordered content blocks."""
    user_message = _latest_user_text(state)
    tool_result = state.get("tool_result") or ""

    # Extract the final assistant answer from messages
    final_answer = ""
    raw_messages = list(state.get("messages") or [])
    for msg in reversed(raw_messages):
        msg_type = getattr(msg, "type", None)
        msg_content = getattr(msg, "content", None)
        if msg_type == "ai" and isinstance(msg_content, str) and msg_content.strip():
            if not msg_content.startswith("Action:") and not msg_content.startswith("Observation"):
                final_answer = msg_content
                break

    analysis_parts = []
    if tool_result:
        analysis_parts.append(f"=== Raw tool data ===\n{tool_result[:3000]}")
    if final_answer:
        analysis_parts.append(f"=== Agent's final answer ===\n{final_answer[:3000]}")
    analysis_text = "\n\n".join(analysis_parts) if analysis_parts else ""

    llm = _build_llm(streaming=False)

    from graph.chart_planner import plan_charts
    from graph.chart_generator import generate_chart_spec

    chart_intents = await plan_charts(llm, user_message, analysis_text)
    logger.info("Chart intents: %s", chart_intents)

    chart_specs = []
    for intent in chart_intents:
        spec = await generate_chart_spec(llm, user_message, tool_result, intent)
        if spec:
            chart_specs.append(spec)
    logger.info("Chart specs generated: %d", len(chart_specs))

    # Compose answer + charts into ordered content blocks
    from graph.content_composer import compose_blocks

    blocks = await compose_blocks(llm, user_message, final_answer, chart_specs)
    logger.info("Content blocks composed: %d blocks", len(blocks))

    return {
        "chart_specs": chart_specs,
        "blocks": blocks,
    }
