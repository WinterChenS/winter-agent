from __future__ import annotations

import json
import time
from typing import Any, TypedDict

from observability.trace import TraceContext

SCHEMA_VERSION = "1.0"


class EventEnvelope(TypedDict):
    type: str
    schemaVersion: str
    conversationId: str
    turnId: str
    agentId: str
    traceId: str
    spanId: str
    timestamp: int
    payload: dict[str, Any]


def build_envelope(
    event_type: str,
    trace_ctx: TraceContext,
    payload: dict[str, Any] | None = None,
    compat_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "type": event_type,
        "schemaVersion": SCHEMA_VERSION,
        "conversationId": trace_ctx.conversation_id,
        "turnId": trace_ctx.turn_id,
        "agentId": trace_ctx.agent_id,
        "traceId": trace_ctx.trace_id,
        "spanId": trace_ctx.span_id,
        "timestamp": int(time.time() * 1000),
        "payload": payload or {},
    }

    if compat_fields:
        envelope.update({k: v for k, v in compat_fields.items() if v is not None})

    return envelope


def envelope_token(trace_ctx: TraceContext, content: str, *, event_type: str = "token") -> dict[str, Any]:
    return build_envelope(
        event_type,
        trace_ctx,
        payload={"content": content},
        compat_fields={"token": content, "content": content},
    )


def envelope_reasoning_delta(trace_ctx: TraceContext, content: str) -> dict[str, Any]:
    return build_envelope(
        "reasoning_delta",
        trace_ctx,
        payload={"content": content},
        compat_fields={"content": content},
    )


def envelope_tool_start(
    trace_ctx: TraceContext,
    tool_name: str,
    content: str,
    input_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_envelope(
        "tool_start",
        trace_ctx,
        payload={
            "toolName": tool_name,
            "content": content,
            "input": input_payload or {},
            "status": "running",
        },
        compat_fields={"toolName": tool_name, "content": content},
    )


def envelope_tool_result(
    trace_ctx: TraceContext,
    tool_name: str,
    content: str,
    *,
    status: str | None = None,
    input_text: str | None = None,
    elapsed_ms: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return build_envelope(
        "tool_result",
        trace_ctx,
        payload={
            "toolName": tool_name,
            "content": content,
            "summary": content,
            "status": status or "completed",
            "input": input_text or "",
            "elapsed_ms": elapsed_ms or 0,
            "error": error,
        },
        compat_fields={"toolName": tool_name, "content": content},
    )


def envelope_tool_summary(trace_ctx: TraceContext, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return build_envelope(
        "tool_summary",
        trace_ctx,
        payload={"steps": steps},
        compat_fields={"steps": steps},
    )


def envelope_agent_step(trace_ctx: TraceContext, reason: dict[str, Any]) -> dict[str, Any]:
    return build_envelope(
        "agent_step",
        trace_ctx,
        payload={"reason": reason},
        compat_fields={"reason": reason},
    )


def envelope_chart(trace_ctx: TraceContext, chart_spec: dict[str, Any]) -> EventEnvelope:
    """Build a 'chart' event envelope carrying ChartSpec to the frontend."""
    return build_envelope(
        event_type="chart",
        trace_ctx=trace_ctx,
        payload={"chartSpec": chart_spec},
        compat_fields={"chartSpec": chart_spec},
    )


def envelope_error(trace_ctx: TraceContext, message: str) -> dict[str, Any]:
    return build_envelope(
        "error",
        trace_ctx,
        payload={"error": message},
        compat_fields={"error": message},
    )


def to_sse_data(envelope: dict[str, Any]) -> dict[str, str]:
    return {"data": json.dumps(envelope, ensure_ascii=False)}


def envelope_message_delta(
    trace_ctx: TraceContext, message_id: str, delta: str
) -> dict[str, Any]:
    """message.delta — token-level text increment."""
    return build_envelope(
        "message.delta",
        trace_ctx,
        payload={"messageId": message_id, "agentId": trace_ctx.agent_id, "delta": delta},
        compat_fields={"messageId": message_id, "delta": delta},
    )


def envelope_message_tool_call(
    trace_ctx: TraceContext, message_id: str, tool_call: dict[str, Any]
) -> dict[str, Any]:
    """message.tool_call — tool invocation status update."""
    return build_envelope(
        "message.tool_call",
        trace_ctx,
        payload={
            "messageId": message_id,
            "agentId": trace_ctx.agent_id,
            "toolCall": tool_call,
        },
        compat_fields={"messageId": message_id, "toolCall": tool_call},
    )


def envelope_message_reasoning(
    trace_ctx: TraceContext, message_id: str, delta: str
) -> dict[str, Any]:
    """message.reasoning — AI thinking process increment."""
    return build_envelope(
        "message.reasoning",
        trace_ctx,
        payload={"messageId": message_id, "agentId": trace_ctx.agent_id, "delta": delta},
        compat_fields={"messageId": message_id, "delta": delta},
    )


def envelope_message_done(
    trace_ctx: TraceContext, message_id: str, *,
    status: str = "done", error: str | None = None,
) -> dict[str, Any]:
    """message.done — stream completion signal."""
    payload: dict[str, Any] = {
        "messageId": message_id,
        "agentId": trace_ctx.agent_id,
        "status": status,
    }
    if error:
        payload["error"] = error
    return build_envelope(
        "message.done",
        trace_ctx,
        payload=payload,
        compat_fields={"messageId": message_id, "status": status},
    )
