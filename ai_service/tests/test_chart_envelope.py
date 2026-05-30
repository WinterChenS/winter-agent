"""
Tests for chart SSE event envelope.
"""
from __future__ import annotations

import json

from domain.event_envelope import envelope_chart, to_sse_data
from observability.trace import ensure_trace_context


class TestEnvelopeChart:
    def _ctx(self, conv_id: str = "conv-chart"):
        return ensure_trace_context(conv_id)

    def test_creates_chart_envelope(self):
        ctx = self._ctx()
        chart_spec = {
            "id": "abc123",
            "title": "Test",
            "chartType": "bar",
            "data": [{"name": "A", "value": 10}],
        }
        envelope = envelope_chart(ctx, chart_spec)

        assert envelope["type"] == "chart"
        assert envelope["conversationId"] == "conv-chart"
        assert envelope["payload"]["chartSpec"] == chart_spec
        assert envelope["chartSpec"] == chart_spec  # compat field

    def test_chart_envelope_has_required_fields(self):
        ctx = self._ctx()
        envelope = envelope_chart(ctx, {"id": "x", "title": "T", "chartType": "bar", "data": []})

        required = {
            "type", "schemaVersion", "conversationId", "turnId",
            "agentId", "traceId", "spanId", "timestamp", "payload",
        }
        assert required.issubset(set(envelope.keys()))

    def test_chart_envelope_schema_version(self):
        ctx = self._ctx()
        envelope = envelope_chart(ctx, {"id": "x"})
        assert envelope["schemaVersion"] == "1.0"

    def test_sse_serialization(self):
        ctx = self._ctx()
        chart_spec = {
            "id": "abc",
            "title": "Chart",
            "chartType": "pie",
            "data": [{"name": "A", "value": 30}],
        }
        envelope = envelope_chart(ctx, chart_spec)
        sse = to_sse_data(envelope)

        assert "data" in sse
        decoded = json.loads(sse["data"])
        assert decoded["type"] == "chart"
        assert decoded["chartSpec"]["chartType"] == "pie"
        assert decoded["conversationId"] == "conv-chart"

    def test_sse_serialization_roundtrip(self):
        ctx = self._ctx()
        chart_spec = {
            "id": "roundtrip",
            "title": "Roundtrip Test",
            "chartType": "line",
            "description": "Testing",
            "xAxisLabel": "X",
            "yAxisLabel": "Y",
            "data": [
                {"name": "P1", "value": 10.5, "group": "G1"},
                {"name": "P2", "value": 20.3, "group": "G2"},
            ],
        }
        envelope = envelope_chart(ctx, chart_spec)
        sse = to_sse_data(envelope)
        decoded = json.loads(sse["data"])

        assert decoded["chartSpec"] == chart_spec
        assert decoded["type"] == "chart"

    def test_different_conversation_ids(self):
        ctx1 = self._ctx("conv-a")
        ctx2 = self._ctx("conv-b")
        spec = {"id": "x", "title": "T", "chartType": "bar", "data": []}

        e1 = envelope_chart(ctx1, spec)
        e2 = envelope_chart(ctx2, spec)

        assert e1["conversationId"] == "conv-a"
        assert e2["conversationId"] == "conv-b"
