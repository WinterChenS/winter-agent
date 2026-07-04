from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, replace
from typing import Any

from domain.event_envelope import (
    build_envelope,
    envelope_agent_step,
    envelope_chart,
    envelope_message_delta,
    envelope_message_reasoning,
    envelope_message_tool_call,
    envelope_tool_completed,
    envelope_tool_output,
    envelope_tool_progress,
    envelope_tool_summary,
)
from core.streaming_event_bus import StreamingEvent
from observability.trace import TraceContext, new_span


@dataclass(frozen=True)
class EventMapContext:
    trace_ctx: TraceContext
    known_tools: set[str]




def summarize_tool_result(tool_name: str, output: dict[str, Any]) -> str:
    tool_result_raw = output.get("tool_result")
    if isinstance(tool_result_raw, str):
        try:
            parsed = json.loads(tool_result_raw)
        except Exception:
            parsed = None
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


# Track tool_call_id by span_id across function calls (unique per connection+tool)
_active_tool_call_ids: dict[str, str] = {}


def map_langgraph_event_to_envelopes(
    event: dict[str, Any],
    ctx: EventMapContext,
    active_tool_span_id: str | None,
    message_id: str = "",
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any] | None]:
    envelopes: list[dict[str, Any]] = []
    final_state: dict[str, Any] | None = None

    event_type = event.get("event")
    event_name = event.get("name")

    if event_type == "on_chat_model_stream":
        # Only forward stream tokens from answer_node or non-graph LLM calls.
        # Router and collaboration LLM calls are internal — their output
        # goes through the pipeline, not directly to the user.
        node_name = (event.get("metadata") or {}).get("langgraph_node", "")
        allowed_nodes = {"answer", "agent", "chart_planner", "composer", "planning", "execution"}
        if node_name and node_name not in allowed_nodes:
            return envelopes, active_tool_span_id, final_state

        chunk = event.get("data", {}).get("chunk")
        content = getattr(chunk, "content", "")
        if content:
            envelopes.append(envelope_message_delta(ctx.trace_ctx, message_id, content))

        # Reasoning content (single source with fallback to avoid double-emission)
        additional_kwargs = getattr(chunk, "additional_kwargs", {}) or {}
        reasoning = (
            getattr(chunk, "reasoning_content", None)
            or getattr(chunk, "reasoning", None)
            or additional_kwargs.get("reasoning_content", "")
            or ""
        )
        if reasoning:
            envelopes.append(envelope_message_reasoning(ctx.trace_ctx, message_id, reasoning))

    elif event_type == "on_chain_start" and event_name == "tool":
        input_state = event.get("data", {}).get("input", {})
        tool_name = "unknown"
        input_payload: dict[str, Any] = {}
        if isinstance(input_state, dict):
            tool_name = input_state.get("current_tool") or tool_name
            input_payload = {k: v for k, v in input_state.items() if k != "current_tool"}

        active_tool_span_id = new_span(ctx.trace_ctx.span_id, name=f"tool:{tool_name}")
        tool_call_id = uuid.uuid4().hex[:12]
        _active_tool_call_ids[active_tool_span_id] = tool_call_id

        tool_ctx = replace(ctx.trace_ctx, span_id=active_tool_span_id,
                          parent_span_id=ctx.trace_ctx.span_id)
        envelopes.append(
            envelope_message_tool_call(tool_ctx, message_id, {
                "id": tool_call_id,
                "name": tool_name,
                "arguments": input_payload,
                "status": "running",
            })
        )

    elif event_type == "on_chain_end" and event_name == "tool":
        output_state = event.get("data", {}).get("output", {})
        input_state = event.get("data", {}).get("input", {})
        tool_name = "tool"
        if isinstance(output_state, dict):
            tool_name = output_state.get("current_tool") or tool_name
        if tool_name == "tool" and isinstance(input_state, dict):
            tool_name = input_state.get("current_tool") or tool_name

        tool_call_id = _active_tool_call_ids.pop(active_tool_span_id, "")

        summary = summarize_tool_result(tool_name, output_state if isinstance(output_state, dict) else {})
        tool_ctx = replace(
            ctx.trace_ctx,
            span_id=active_tool_span_id or new_span(ctx.trace_ctx.span_id, name=f"tool:{tool_name}"),
            parent_span_id=ctx.trace_ctx.span_id,
        )
        envelopes.append(envelope_message_tool_call(tool_ctx, message_id, {
            "id": tool_call_id,
            "name": tool_name,
            "status": "done",
            "result": f"{summary}\n\n",
        }))
        active_tool_span_id = None

    elif event_type == "on_chain_end":
        output_state = event.get("data", {}).get("output", {})
        if isinstance(output_state, dict):
            # Capture state from agent, chart_planner, collaboration, and answer nodes
            if "messages" in output_state or "chart_specs" in output_state or "collab_result" in output_state:
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


def map_streaming_bus_event_to_envelope(
    event: StreamingEvent,
    ctx: EventMapContext,
    message_id: str,
) -> dict[str, Any] | None:
    if event.type == "tool.started":
        tool_name = event.data.get("toolName", "unknown")
        tc_id = event.data.get("tool_call_id") or f"{tool_name}_{event.timestamp}"
        return build_envelope(
            "tool.started",
            ctx.trace_ctx,
            payload={
                "tool_call_id": tc_id,
                "tool": tool_name,
                "arguments": event.data.get("arguments", {}),
                "status": "running",
            },
        )
    elif event.type == "tool.progress":
        return envelope_tool_progress(
            ctx.trace_ctx,
            tool_name=event.data.get("toolName", "unknown"),
            progress=event.data.get("progress", 0),
            message=event.data.get("message", ""),
        )
    elif event.type == "tool.output":
        tool_name = event.data.get("toolName", "unknown")
        tc_id = f"{tool_name}_{event.timestamp}"
        return build_envelope(
            "tool.output",
            ctx.trace_ctx,
            payload={
                "tool_call_id": tc_id,
                "tool": tool_name,
                "output": event.data.get("output", ""),
                "chunkIndex": event.data.get("chunkIndex", 0),
            },
        )
    elif event.type == "tool.completed":
        tool_name = event.data.get("toolName", "unknown")
        tc_id = event.data.get("tool_call_id") or f"{tool_name}_{event.timestamp}"
        result_data = event.data.get("result", {})
        if isinstance(result_data, dict) and result_data.get("ok"):
            summary = summarize_tool_result(tool_name, result_data)
        else:
            summary = str(result_data.get("error", {}).get("message", "")) if isinstance(result_data, dict) else ""
        return build_envelope(
            "tool.finished",
            ctx.trace_ctx,
            payload={
                "tool_call_id": tc_id,
                "tool": tool_name,
                "result": {"status": "completed", "summary": summary, "elapsed_ms": event.data.get("elapsed_ms", 0)},
            },
        )
    return None


