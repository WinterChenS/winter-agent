from __future__ import annotations
from api.events.event_mapper import EventMapContext, emit_chart_envelopes
from observability.trace import ensure_trace_context

def _ctx(cid="cm"):
    return EventMapContext(trace_ctx=ensure_trace_context(cid), known_tools={"search", "browser"})

class TestEmitChartEnvelopes:
    def test_none_state(self):
        assert emit_chart_envelopes(None, _ctx()) == []

    def test_non_dict_state(self):
        assert emit_chart_envelopes("str", _ctx()) == []

    def test_no_chart_spec(self):
        assert emit_chart_envelopes({"messages": []}, _ctx()) == []

    def test_empty_chart_specs(self):
        assert emit_chart_envelopes({"chart_specs": []}, _ctx()) == []

    def test_valid_chart_specs(self):
        cs = {"id": "1", "title": "Scores", "chartType": "bar", "data": [{"name": "A", "value": 10}]}
        r = emit_chart_envelopes({"chart_specs": [cs]}, _ctx("conv-ec"))
        assert len(r) == 1
        assert r[0]["type"] == "chart"
        assert r[0]["chartSpec"] == cs

    def test_multiple_charts(self):
        r = emit_chart_envelopes({"chart_specs": [{"id":"1","chartType":"line","data":[]},{"id":"2","chartType":"pie","data":[]}]}, _ctx())
        assert len(r) == 2

    def test_legacy_fallback(self):
        r = emit_chart_envelopes({"chart_spec": {"id":"1","chartType":"bar","data":[]}}, _ctx())
        assert len(r) == 1
