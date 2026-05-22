from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from urllib.parse import urlparse

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import settings
from core.runtime import get_tool_registry
from graph.state import State

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# 工具调用时，LLM 需要返回的 JSON 格式说明（写在 system prompt 里）
# ────────────────────────────────────────────────────────────────────────────
_TOOL_FORMAT_HINT = """\
You can call ONE tool per response. To call a tool respond with ONLY this JSON (no markdown, no extra text):
{"action": "tool", "tool": "<tool_name>", "query": "<your query>"}

Rules for tool use:
- For ANY question about current time or date → call the "time" tool first.
- For news, weather, events, or anything with "latest / today / recent / now" →
  first confirm today's date using the "time" tool (unless today's date is already
  known from a previous tool result), then search with the exact date in the query
  (e.g. "2026-05-20 今日大新闻").
- Never call the same tool repeatedly with the same intent in one turn.
- If the time has already been obtained in this turn, DO NOT call "time" again.
- You may chain tool calls: each response either calls one tool OR gives a final answer.
- If you already have enough information, reply normally in plain text.\
"""

# Maximum number of tool calls in one turn to avoid infinite loops.
MAX_ITERATIONS = 5


def _build_llm() -> ChatOpenAI:
    """创建并返回 ChatOpenAI 实例（集中在一处，方便统一修改参数）。"""
    return ChatOpenAI(
        model=settings.model,
        temperature=settings.temperature,
        streaming=True,
        api_key=settings.api_key,
        base_url=settings.base_url,
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


def _sanitize_tool_result_for_prompt(tool_result: str | None) -> str:
    """Build a safe, compact tool context to avoid sending raw tool payload to provider."""
    if not tool_result:
        return ""

    try:
        parsed = json.loads(tool_result)
    except Exception:
        # Raw text may trigger provider inspection; keep only short neutral prefix.
        return "Tool returned data (sanitized)."

    if not isinstance(parsed, dict):
        return "Tool returned structured data (sanitized)."

    ok = bool(parsed.get("ok", False))
    if not ok:
        err = str(parsed.get("error") or parsed.get("message") or "unknown error")[:200]
        return f"Tool execution failed: {err}"

    data = parsed.get("data")

    # time 工具常见返回：data 是时间字符串
    if isinstance(data, str):
        compact = " ".join(data.split())[:120]
        if compact:
            return f"time: {compact}"
        return "time: (available)"

    data = data if isinstance(data, dict) else {}
    query = str(data.get("query") or "").strip()
    results = data.get("results") if isinstance(data.get("results"), list) else []

    lines: list[str] = []
    if query:
        lines.append(f"query: {query[:120]}")
    lines.append(f"result_count: {len(results)}")

    # Only keep title + domain; drop full snippet content to reduce inspection risk.
    for idx, item in enumerate(results[:3], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()[:120]
        url = str(item.get("url") or "").strip()
        domain = ""
        if url:
            try:
                domain = urlparse(url).netloc[:80]
            except Exception:
                domain = ""
        if title or domain:
            lines.append(f"{idx}. title={title or '-'}; source={domain or '-'}")

    return "\n".join(lines) if lines else "Tool returned structured data (sanitized)."


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
    tool_result_sanitized = _sanitize_tool_result_for_prompt(tool_result)
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
        step = "[agent_node] LLM invoke failed; returned local fallback final answer."
        return {
            "messages": [AIMessage(content=fallback)],
            "current_tool": None,
            "tool_input": None,
            "reasoning_steps": state.get("reasoning_steps", []) + [step],
        }

    # 5. 尝试解析是否要调工具
    content = (response.content or "").strip()
    try:
        parsed = _parse_tool_call(content)
        if parsed:
            tool_name, query = parsed
            normalized_query = _normalize_query(query)

            if current_iteration >= MAX_ITERATIONS:
                fallback = "我已完成多次工具检索，下面基于现有结果给出最终结论。"
                if tool_result_sanitized:
                    fallback += f"\n\n（最新工具结果）\n{tool_result_sanitized}"
                step = (
                    f"[agent_node] Tool call limit reached ({MAX_ITERATIONS}), "
                    "forced final answer generation."
                )
                return {
                    "messages": [AIMessage(content=fallback)],
                    "current_tool": None,
                    "tool_input": None,
                    "reasoning_steps": state.get("reasoning_steps", []) + [step],
                }

            # 通用去重：同一轮里如果重复同一工具同一query，直接收敛
            last_tool_name = (state.get("last_tool_name") or "").strip().lower()
            last_tool_query = _normalize_query(str(state.get("last_tool_query") or ""))
            if last_tool_name == tool_name.lower() and last_tool_query == normalized_query:
                step = (
                    f"[agent_node] Prevented duplicate tool call: tool='{tool_name}', query='{query}'."
                )
                fallback = _build_local_final_fallback(tool_result)
                return {
                    "messages": [AIMessage(content=fallback)],
                    "current_tool": None,
                    "tool_input": None,
                    "reasoning_steps": state.get("reasoning_steps", []) + [step],
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
                    step = (
                        "[agent_node] Prevented repeated time tool call; "
                        f"auto-switched to search with date {date_hint}."
                    )
                    auto_query = f"{date_hint} {latest_user}".strip()
                    return {
                        "current_tool": "search",
                        "tool_input": {"query": auto_query},
                        "tool_result": None,
                        "iteration_count": current_iteration + 1,
                        "last_tool_name": "search",
                        "last_tool_query": auto_query,
                        "reasoning_steps": state.get("reasoning_steps", []) + [step],
                    }

                # 非时效检索场景：直接结束，避免无意义 time 循环
                step = "[agent_node] Prevented repeated time tool call; returned final answer."
                return {
                    "messages": [AIMessage(content=f"当前时间已获取：{tool_result_sanitized.replace('time: ', '', 1)}")],
                    "current_tool": None,
                    "tool_input": None,
                    "reasoning_steps": state.get("reasoning_steps", []) + [step],
                }

            step = f"[agent_node] Decided to call tool '{tool_name}' with query: '{query}'"
            return {
                "current_tool": tool_name,
                "tool_input": {"query": query},
                "tool_result": None,
                "iteration_count": current_iteration + 1,
                "last_tool_name": tool_name,
                "last_tool_query": query,
                "reasoning_steps": state.get("reasoning_steps", []) + [step],
            }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass

    # 6. 普通文本回答
    step = "[agent_node] Generated direct answer (no tool needed)."
    return {
        "messages": [response],
        "current_tool": None,
        "tool_input": None,
        "last_tool_name": None,
        "last_tool_query": None,
        "reasoning_steps": state.get("reasoning_steps", []) + [step],
    }


# ────────────────────────────────────────────────────────────────────────────
# tool_node：工具执行节点
# ────────────────────────────────────────────────────────────────────────────
async def tool_node(state: State) -> dict:
    tool_name = state.get("current_tool") or ""
    tool_input = state.get("tool_input") or {}
    start_time = time.time()

    registry = get_tool_registry()
    if not registry:
        result = {"ok": False, "error": "ToolRegistry not initialized", "code": "REGISTRY_NOT_READY"}
        result_str = json.dumps(result, ensure_ascii=False)
        step = f"[tool_node] ERROR: registry not available, skipped '{tool_name}'"
        status = "error"
        error_msg = "ToolRegistry not initialized"
    else:
        try:
            result = await registry.invoke(tool_name, tool_input)
        except Exception as exc:
            logger.exception("tool_node invoke failed for tool=%s", tool_name)
            result = {
                "ok": False,
                "error": f"tool invoke exception: {str(exc)[:200]}",
                "code": "TOOL_INVOKE_EXCEPTION",
            }

        result_str = json.dumps(result, ensure_ascii=False)
        ok = result.get("ok", False)
        status = "completed" if ok else "error"
        error_msg = result.get("error") if not ok else None
        step = (
            f"[tool_node] Tool '{tool_name}' executed successfully."
            if ok
            else f"[tool_node] Tool '{tool_name}' returned error: {error_msg}"
        )

    elapsed_time = time.time() - start_time
    tool_step_record = {
        "tool": tool_name,
        "input": tool_input.get("query", "") if isinstance(tool_input, dict) else str(tool_input),
        "status": status,
        "elapsed_ms": int(elapsed_time * 1000),
        "timestamp": start_time,
    }
    if status == "error" and error_msg:
        tool_step_record["error"] = error_msg

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
    safe_ctx = _sanitize_tool_result_for_prompt(tool_result)
    if not safe_ctx:
        return "我已经完成工具调用，但生成最终回答时遇到策略限制。请重试一次，或换一个更具体的问题。"
    return (
        "我已完成工具查询。由于模型安全审查或策略限制，我先给出基于工具结果的简要结论：\n\n"
        f"{safe_ctx}\n\n"
        "如果你愿意，我可以继续基于该结果输出更详细的结构化总结。"
    )
