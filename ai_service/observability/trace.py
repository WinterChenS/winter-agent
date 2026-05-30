from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class TraceContext:
    conversation_id: str
    trace_id: str
    turn_id: str
    span_id: str
    parent_span_id: str | None
    agent_id: str


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def ensure_trace_context(conversation_id: str | None, agent_id: str = "agent.main") -> TraceContext:
    conv_id = conversation_id or "default-thread"
    return TraceContext(
        conversation_id=conv_id,
        trace_id=_new_id("trc"),
        turn_id=_new_id("turn"),
        span_id=_new_id("spn"),
        parent_span_id=None,
        agent_id=agent_id,
    )


def new_span(parent_span_id: str, name: str = "child") -> str:
    # Keep span IDs opaque while preserving readable intent in logs/debugging.
    _ = parent_span_id
    _ = name
    return _new_id("spn")

