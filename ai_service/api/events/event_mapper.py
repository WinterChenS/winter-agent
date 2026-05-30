from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

from domain.event_envelope import (
    envelope_agent_step,
    envelope_chart,
    envelope_token,
    envelope_tool_result,
    envelope_tool_start,
    envelope_tool_summary,
)
from observability.trace import TraceContext, new_span


@dataclass(frozen=True)
class EventMapContext:
    trace_ctx: TraceContext
    known_tools: set[str]


def _stream_event_with_content(content: str) -> dict[str, Any]:
    class _Chunk:
        def __init__(self, text: str):
            self.content = text

    return {
        "event": "on_chat_model_stream",
        "data": {"chunk": _Chunk(content)},
    }


def safe_json_loads(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def is_tool_action_json(raw: str, known_tools: set[str]) -> bool:
    parsed = safe_json_loads(raw.strip())
    if not parsed:
        return False

    action = str(parsed.get("action", "")).strip().lower()
    if not action:
        return False

    if action == "tool":
        tool_name = str(parsed.get("tool", "")).strip().lower()
        if not tool_name:
            return False
        return tool_name in known_tools if known_tools else True

    return action in known_tools


def process_stream_token_event(
    event: dict[str, Any],
    collecting_control_json: bool,
    control_json_buffer: str,
    known_tools: set[str],
    preamble_buffer: str = "",
) -> tuple[dict[str, Any] | None, bool, str, str, str]:
    """Filter tool-control JSON from model stream.

    Text tokens stream freely. JSON tool calls are filtered.
    Returns:
      - rewritten event (or None when chunk should be swallowed)
      - updated collecting_control_json
      - updated control_json_buffer
      - updated preamble_buffer (unused, kept for compat)
      - thought_text (non-empty when reasoning text precedes a tool call)
    """
    if event.get("event") != "on_chat_model_stream":
        return event, collecting_control_json, control_json_buffer, preamble_buffer, ""

    chunk = event.get("data", {}).get("chunk")
    raw_token_content = getattr(chunk, "content", "")
    if not raw_token_content:
        return event, collecting_control_json, control_json_buffer, preamble_buffer, ""

    if collecting_control_json:
        merged = control_json_buffer + raw_token_content
        if "}" not in merged:
            return None, True, merged, preamble_buffer, ""
        if is_tool_action_json(merged, known_tools):
            thought = preamble_buffer.strip()
            return None, False, "", "", thought
        return _stream_event_with_content(merged), False, "", "", ""

    if raw_token_content.lstrip().startswith("{"):
        if "}" not in raw_token_content:
            return None, True, raw_token_content, preamble_buffer, ""
        if is_tool_action_json(raw_token_content, known_tools):
            return None, False, "", "", ""
        return _stream_event_with_content(raw_token_content), False, "", "", ""

    # Filter thinking tags and XML function call leaks
    if any(tag in raw_token_content for tag in ("[Thought]", "[/Thought]", "<function>", "</function>", "<query>", "</query>")):
        return None, collecting_control_json, control_json_buffer, preamble_buffer, ""

    # Short preamble buffer: buffer first ~200 chars to detect tool-call vs direct answer.
    # If a '{' appears within the buffer window, the preamble is reasoning → emit as thought.
    # If no '{' appears → release as normal tokens (direct answer).
    new_preamble = preamble_buffer + raw_token_content
    if len(new_preamble) < 200:
        # Still within buffer window — keep buffering to detect tool calls
        return None, False, "", new_preamble, ""
    # Buffer full — release the buffered text and continue streaming
    release_event = _stream_event_with_content(new_preamble)
    return release_event, False, "", "", ""


def summarize_tool_result(tool_name: str, output: dict[str, Any]) -> str:
    tool_result_raw = output.get("tool_result")
    if isinstance(tool_result_raw, str):
        parsed = safe_json_loads(tool_result_raw)
    elif isinstance(tool_result_raw, dict):
        parsed = tool_result_raw
    else:
        parsed = None

    if not parsed:
        return f"工具 `{tool_name}` 执行完成。"

    if not parsed.get("ok", False):
        err = parsed.get("error")
        return f"工具 `{tool_name}` 执行失败：{err}"

    data = parsed.get("data") or {}

    # Browser tool result: {url, title, text, length}
    if "url" in data and "text" in data:
        title = str(data.get("title", "Untitled"))[:80]
        length = int(data.get("length", 0))
        return f"工具 `{tool_name}` 执行完成，读取 {length} 字符（{title}）。"

    query = data.get("query") if isinstance(data, dict) else None
    results = data.get("results") if isinstance(data, dict) else None
    if isinstance(results, list):
        return f"工具 `{tool_name}` 执行完成，命中 {len(results)} 条结果（query: {query or '-'}）。"

    return f"工具 `{tool_name}` 执行成功。"


def extract_last_assistant_text(final_state: dict[str, Any] | None) -> str:
    if not isinstance(final_state, dict):
        return ""

    raw_messages = final_state.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        return ""

    for msg in reversed(raw_messages):
        msg_type = getattr(msg, "type", None)
        msg_content = getattr(msg, "content", None)
        if msg_type == "ai" and isinstance(msg_content, str) and msg_content.strip():
            return msg_content

        if isinstance(msg, dict):
            role = msg.get("role") or msg.get("type")
            content = msg.get("content")
            if role in {"assistant", "ai"} and isinstance(content, str) and content.strip():
                return content

    return ""


def map_langgraph_event_to_envelopes(
    event: dict[str, Any],
    ctx: EventMapContext,
    active_tool_span_id: str | None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any] | None]:
    envelopes: list[dict[str, Any]] = []
    final_state: dict[str, Any] | None = None

    event_type = event.get("event")
    event_name = event.get("name")

    if event_type == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk")
        content = getattr(chunk, "content", "")
        if content:
            envelopes.append(envelope_token(ctx.trace_ctx, content))

    elif event_type == "on_chain_start" and event_name == "tool":
        input_state = event.get("data", {}).get("input", {})
        tool_name = "unknown"
        if isinstance(input_state, dict):
            tool_name = input_state.get("current_tool") or tool_name

        active_tool_span_id = new_span(ctx.trace_ctx.span_id, name=f"tool:{tool_name}")
        tool_ctx = replace(ctx.trace_ctx, span_id=active_tool_span_id, parent_span_id=ctx.trace_ctx.span_id)
        envelopes.append(
            envelope_tool_start(
                tool_ctx,
                tool_name,
                f"\n\n🛠️ 正在调用工具：{tool_name}...\n",
            )
        )

    elif event_type == "on_chain_end" and event_name == "tool":
        output_state = event.get("data", {}).get("output", {})
        input_state = event.get("data", {}).get("input", {})
        tool_name = "tool"
        if isinstance(output_state, dict):
            tool_name = output_state.get("current_tool") or tool_name
        if tool_name == "tool" and isinstance(input_state, dict):
            tool_name = input_state.get("current_tool") or tool_name

        summary = summarize_tool_result(tool_name, output_state if isinstance(output_state, dict) else {})
        tool_ctx = replace(
            ctx.trace_ctx,
            span_id=active_tool_span_id or new_span(ctx.trace_ctx.span_id, name=f"tool:{tool_name}"),
            parent_span_id=ctx.trace_ctx.span_id,
        )
        envelopes.append(envelope_tool_result(tool_ctx, tool_name, f"{summary}\n\n"))
        active_tool_span_id = None

    elif event_type == "on_chain_end":
        output_state = event.get("data", {}).get("output", {})
        if isinstance(output_state, dict):
            if "messages" in output_state:
                final_state = output_state
            elif "blocks" in output_state and isinstance(final_state, dict):
                final_state["blocks"] = output_state["blocks"]
                final_state["chart_specs"] = output_state.get("chart_specs", [])
            elif "blocks" in output_state:
                final_state = output_state
            elif "chart_specs" in output_state and isinstance(final_state, dict):
                final_state["chart_specs"] = output_state["chart_specs"]
            elif "chart_specs" in output_state:
                final_state = output_state

    return envelopes, active_tool_span_id, final_state


def emit_final_summary_envelope(final_state: dict[str, Any] | None, ctx: EventMapContext) -> dict[str, Any] | None:
    if not final_state:
        return None

    tool_steps = final_state.get("tool_steps", [])
    if not tool_steps:
        return None

    return envelope_tool_summary(ctx.trace_ctx, tool_steps)


def emit_guard_reason_envelope(final_state: dict[str, Any] | None, ctx: EventMapContext) -> dict[str, Any] | None:
    if not final_state:
        return None
    reason = final_state.get("last_guard_reason")
    if not isinstance(reason, dict) or not reason:
        return None
    return envelope_agent_step(ctx.trace_ctx, reason)


def emit_chart_envelopes(
    final_state: dict[str, Any] | None,
    ctx: EventMapContext,
) -> list[dict[str, Any]]:
    """Emit chart envelopes for all chart specs in the final state (multi-chart support)."""
    if not isinstance(final_state, dict):
        return []
    # Support both new "chart_specs" (list) and legacy "chart_spec" (single dict)
    specs = final_state.get("chart_specs")
    if isinstance(specs, list) and specs:
        return [envelope_chart(ctx.trace_ctx, s) for s in specs if isinstance(s, dict) and s]
    # Legacy fallback
    single = final_state.get("chart_spec")
    if isinstance(single, dict) and single:
        return [envelope_chart(ctx.trace_ctx, single)]
    return []


