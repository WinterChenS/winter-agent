import json

from domain.event_envelope import build_envelope, envelope_token, to_sse_data
from observability.trace import ensure_trace_context


def test_required_fields_present():
    ctx = ensure_trace_context("conv-1")
    envelope = build_envelope("token", ctx, payload={"content": "hello"})

    required = {
        "type",
        "schemaVersion",
        "conversationId",
        "turnId",
        "agentId",
        "traceId",
        "spanId",
        "timestamp",
        "payload",
    }
    assert required.issubset(set(envelope.keys()))
    assert envelope["conversationId"] == "conv-1"


def test_compat_flat_fields_dual_write():
    ctx = ensure_trace_context("conv-2")
    envelope = envelope_token(ctx, "hi")

    assert envelope["type"] == "token"
    assert envelope["payload"]["content"] == "hi"
    assert envelope["content"] == "hi"
    assert envelope["token"] == "hi"


def test_payload_preserves_structured_data():
    ctx = ensure_trace_context("conv-3")
    envelope = build_envelope("tool_summary", ctx, payload={"steps": [{"tool": "search"}]})
    sse = to_sse_data(envelope)
    decoded = json.loads(sse["data"])

    assert decoded["payload"]["steps"][0]["tool"] == "search"

