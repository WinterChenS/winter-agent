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


def envelope_tool_start(trace_ctx: TraceContext, tool_name: str, content: str) -> dict[str, Any]:
    return build_envelope(
        "tool_start",
        trace_ctx,
        payload={"toolName": tool_name, "content": content},
        compat_fields={"toolName": tool_name, "content": content},
    )


def envelope_tool_result(trace_ctx: TraceContext, tool_name: str, content: str) -> dict[str, Any]:
    return build_envelope(
        "tool_result",
        trace_ctx,
        payload={"toolName": tool_name, "content": content},
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


def envelope_block(trace_ctx: TraceContext, block: dict[str, Any]) -> EventEnvelope:
    """Build a 'block' event envelope carrying a content block to the frontend."""
    return build_envelope(
        event_type="block",
        trace_ctx=trace_ctx,
        payload={"block": block},
        compat=block,
    )


def envelope_chart_placeholder(trace_ctx: TraceContext, chart_id: str) -> EventEnvelope:
    """Build a 'chart_placeholder' event — frontend shows a loading skeleton."""
    return build_envelope(
        event_type="chart_placeholder",
        trace_ctx=trace_ctx,
        payload={"chartId": chart_id},
        compat={"chartId": chart_id},
    )


def envelope_chart_ready(trace_ctx: TraceContext, chart_id: str, chart_spec: dict[str, Any]) -> EventEnvelope:
    """Build a 'chart_ready' event — frontend replaces placeholder with real chart."""
    return build_envelope(
        event_type="chart_ready",
        trace_ctx=trace_ctx,
        payload={"chartId": chart_id, "chartSpec": chart_spec},
        compat={"chartId": chart_id, "chartSpec": chart_spec},
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

