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
# 工具调用时，LLM 需要返回的 JSON 格式说明（写在 system prompt 里）
# ────────────────────────────────────────────────────────────────────────────
_TOOL_FORMAT_HINT = """\
You can call ONE tool per response. To call a tool respond with ONLY this JSON (no markdown, no extra text):
{"action": "tool", "tool": "<tool_name>", "query": "<your query>"}

Rules for tool use:
- For direct current time/date questions, call the "time" tool.
- For news, weather, events, or anything with "latest / today / recent / now":
  prefer calling "search" directly with explicit date if date context is already available.
  Call "time" only when date is truly missing.
- Never call the same tool repeatedly with the same intent in one turn.
- If the time has already been obtained in this turn, DO NOT call "time" again.
- You may chain tool calls: each response either calls one tool OR gives a final answer.
- If you already have enough information, reply normally in plain text.\
"""

# Maximum number of tool calls in one turn to avoid infinite loops.
MAX_ITERATIONS = 5


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


def _tool_result_has_search_hits(tool_result: str | None) -> bool:
    if not tool_result:
        return False
    try:
        parsed = json.loads(tool_result)
    except Exception:
        return False
    if not isinstance(parsed, dict) or not parsed.get("ok", False):
        return False
    data = parsed.get("data")
    if not isinstance(data, dict):
        return False
    results = data.get("results")
    return isinstance(results, list) and len(results) > 0


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


def _build_llm() -> ChatOpenAI:
    """创建并返回 ChatOpenAI 实例（集中在一处，方便统一修改参数）。"""
    return ChatOpenAI(
        model=settings.model,
        temperature=settings.temperature,
        streaming=True,
        api_key=settings.api_key,
        base_url=settings.base_url,
        extra_body={
            "enable_thinking": False
        }
    )


def _parse_tool_call(content: str) -> tuple[str, str] | None:
    """Parse model tool intent JSON and return (tool_name, query)."""
    if not content.startswith("{"):
        return None

    parsed = json.loads(content)
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
    ]
    if tool_result_sanitized:
        guidance.append(f"Tool result context (sanitized):\n{tool_result_sanitized}")
    forced_messages = [SystemMessage(content="\n".join(guidance))] + list(state["messages"])
    response = await llm.ainvoke(forced_messages)
    text = (response.content or "").strip()
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

    # 2. 注入当前真实日期，避免 LLM 以为还是训练截止年份
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    system_lines = [
        "You are a helpful AI assistant.",
        f"Current date and time (server): {now_str}",
    ]
    if tools_desc:
        system_lines.append(f"\nAvailable tools:\n{tools_desc}")
        system_lines.append(_TOOL_FORMAT_HINT)

    # 3. 把上一轮工具结果告知 LLM
    tool_result = state.get("tool_result")
    tool_result_sanitized = normalize_tool_result_for_prompt(tool_result)
    current_iteration = int(state.get("iteration_count", 0) or 0)
    if tool_result_sanitized:
        if current_iteration < MAX_ITERATIONS:
            system_lines.append(
                f"\nTool result (sanitized, iteration {current_iteration}):\n{tool_result_sanitized}\n"
                "You may call another tool if needed, or provide the final answer."
            )
            if tool_result_sanitized.startswith("time:"):
                system_lines.append(
                    "You already have current date/time from tool output. "
                    "Do NOT call time again in this turn; continue with next required tool or final answer."
                )
        else:
            system_lines.append(
                f"\nYou have received the following tool result (sanitized):\n{tool_result_sanitized}\n"
                "Now provide a comprehensive final answer. Do NOT call any more tools."
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
                fallback = "我已完成多次工具检索，下面基于现有结果给出最终结论。"
                if tool_result_sanitized:
                    fallback += f"\n\n（最新工具结果）\n{tool_result_sanitized}"
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

            # Stop unhelpful search loops: if search already returned hits, force final answer.
            if tool_name.lower() == "search" and _tool_result_has_search_hits(tool_result):
                reason = _reason_record(
                    node="agent_node",
                    code="SEARCH_RESULTS_ALREADY_AVAILABLE",
                    message="Search already has results; forced final answer instead of another search.",
                )
                try:
                    forced = await _generate_forced_final_answer(
                        llm=llm,
                        state=state,
                        now_str=now_str,
                        tool_result_sanitized=tool_result_sanitized,
                    )
                except Exception as exc:
                    logger.warning("agent_node search-loop break finalization failed: %s", exc)
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

    return {
        "tool_result": result_str,
        "tool_steps": new_tool_steps,
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
        return "我已经完成工具调用，但暂时无法生成稳定的最终文本。请重试一次，或换一个更具体的问题。"
    return (
        "我已完成工具查询。下面基于工具结果给出简要结论：\n\n"
        f"{safe_ctx}\n\n"
        "如果你愿意，我可以继续基于该结果输出更详细的结构化总结。"
    )
