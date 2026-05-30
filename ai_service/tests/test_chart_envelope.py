"""Tests for chart SSE event envelope."""
from __future__ import annotations

import json
from domain.event_envelope import envelope_chart, to_sse_data
from observability.trace import ensure_trace_context


class TestEnvelopeChart:
    def test_type(self):
        ctx = ensure_trace_context("c1")
        e = envelope_chart(ctx, {"id": "1", "chartType": "line", "data": []})
        assert e["type"] == "chart"
        assert e["conversationId"] == "c1"

    def test_payload(self):
        ctx = ensure_trace_context("c2")
        cs = {"id": "a", "title": "T", "chartType": "bar", "data": [{"name": "X", "value": 10}]}
        e = envelope_chart(ctx, cs)
        assert e["payload"]["chartSpec"] == cs
        assert e["chartSpec"] == cs

    def test_sse_serialization(self):
        ctx = ensure_trace_context("c3")
        e = envelope_chart(ctx, {"id": "z", "chartType": "pie", "data": []})
        sse = to_sse_data(e)
        assert "data" in sse
        parsed = json.loads(sse["data"])
        assert parsed["type"] == "chart"

    def test_required_fields(self):
        ctx = ensure_trace_context("c4")
        e = envelope_chart(ctx, {"chartType": "line", "data": []})
        required = {"type", "schemaVersion", "conversationId", "timestamp", "payload"}
        assert required.issubset(set(e.keys()))

    def test_empty_spec(self):
        ctx = ensure_trace_context("c5")
        e = envelope_chart(ctx, {})
        assert e["type"] == "chart"
