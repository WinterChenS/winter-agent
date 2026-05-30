"""Tests for chart event mapper integration."""
from __future__ import annotations

from api.events.event_mapper import EventMapContext, emit_chart_envelope
from observability.trace import ensure_trace_context


def _ctx(cid="cm"):
    return EventMapContext(trace_ctx=ensure_trace_context(cid), known_tools={"search", "browser"})


class TestEmitChartEnvelope:
    def test_none_state(self):
        assert emit_chart_envelope(None, _ctx()) is None

    def test_non_dict_state(self):
        assert emit_chart_envelope("str", _ctx()) is None

    def test_no_chart_spec(self):
        assert emit_chart_envelope({"messages": []}, _ctx()) is None

    def test_none_chart_spec(self):
        assert emit_chart_envelope({"chart_spec": None}, _ctx()) is None

    def test_empty_chart_spec(self):
        assert emit_chart_envelope({"chart_spec": {}}, _ctx()) is None

    def test_valid_chart_spec(self):
        cs = {"id": "1", "title": "Scores", "chartType": "bar",
              "data": [{"name": "A", "value": 10}]}
        r = emit_chart_envelope({"chart_spec": cs}, _ctx("conv-ec"))
        assert r is not None
        assert r["type"] == "chart"
        assert r["chartSpec"] == cs
        assert r["conversationId"] == "conv-ec"

    def test_chart_spec_with_description(self):
        cs = {"id": "2", "title": "D", "chartType": "pie",
              "description": "A pie", "data": [{"name": "X", "value": 40, "group": "G"}]}
        r = emit_chart_envelope({"chart_spec": cs}, _ctx())
        assert r is not None
        assert len(r["chartSpec"]["data"]) == 1
