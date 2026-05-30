"""
Tests for chart event mapper integration.
"""
from __future__ import annotations

from api.events.event_mapper import (
    EventMapContext,
    emit_chart_envelope,
    map_langgraph_event_to_envelopes,
)
from observability.trace import ensure_trace_context


def _ctx() -> EventMapContext:
    return EventMapContext(trace_ctx=ensure_trace_context("conv-mapper"), known_tools=set())


class TestEmitChartEnvelope:
    def test_returns_none_for_empty_state(self):
        result = emit_chart_envelope(None, _ctx())
        assert result is None

    def test_returns_none_when_no_chart_spec(self):
        result = emit_chart_envelope({"messages": []}, _ctx())
        assert result is None

    def test_returns_none_when_chart_spec_is_none(self):
        result = emit_chart_envelope({"chart_spec": None}, _ctx())
        assert result is None

    def test_returns_none_when_chart_spec_is_empty_dict(self):
        result = emit_chart_envelope({"chart_spec": {}}, _ctx())
        assert result is None

    def test_emits_envelope_when_chart_spec_present(self):
        state = {
            "chart_spec": {
                "id": "abc",
                "title": "Test",
                "chartType": "bar",
                "data": [{"name": "A", "value": 10}],
            },
        }
        envelope = emit_chart_envelope(state, _ctx())
        assert envelope is not None
        assert envelope["type"] == "chart"
        assert envelope["chartSpec"]["title"] == "Test"

    def test_envelope_has_char_spec_in_payload(self):
        state = {
            "chart_spec": {
                "id": "xyz",
                "title": "Scores",
                "chartType": "pie",
                "data": [{"name": "X", "value": 50}],
            },
        }
        envelope = emit_chart_envelope(state, _ctx())
        assert envelope["payload"]["chartSpec"]["title"] == "Scores"

    def test_handles_non_dict_state(self):
        result = emit_chart_envelope("not_a_dict", _ctx())  # type: ignore
        assert result is None


class TestMapLanggraphEventToEnvelopesWithChart:
    def test_captures_chart_spec_from_on_chain_end(self):
        """Verify that on_chain_end with chart_spec merges into final_state."""
        ctx = _ctx()

        # First: simulate an agent on_chain_end with messages (sets final_state)
        event_agent_end = {
            "event": "on_chain_end",
            "name": "agent",
            "data": {
                "output": {
                    "messages": [],
                    "conversation_id": "conv-1",
                }
            },
        }
        _, _, final_state = map_langgraph_event_to_envelopes(event_agent_end, ctx, None)
        assert final_state is not None
        assert "messages" in final_state

        # Second: simulate chart_node on_chain_end with chart_spec (should merge)
        chart_spec_data = {
            "id": "chart1",
            "title": "Chart",
            "chartType": "bar",
            "data": [{"name": "A", "value": 10}],
        }
        event_chart_end = {
            "event": "on_chain_end",
            "name": "chart",
            "data": {
                "output": {
                    "chart_spec": chart_spec_data,
                    "chart_intent": {"need_chart": True},
                }
            },
        }
        _, _, updated_state = map_langgraph_event_to_envelopes(event_chart_end, ctx, None)
        assert updated_state is not None
        assert "chart_spec" in updated_state
        assert updated_state["chart_spec"] == chart_spec_data

    def test_chart_spec_without_messages_creates_standalone_state(self):
        """When chart_spec appears without prior messages state, it creates new state."""
        ctx = _ctx()
        event = {
            "event": "on_chain_end",
            "name": "chart",
            "data": {
                "output": {
                    "chart_spec": {"id": "x", "title": "T", "chartType": "bar", "data": []},
                }
            },
        }
        _, _, final_state = map_langgraph_event_to_envelopes(event, ctx, None)
        assert final_state is not None
        assert "chart_spec" in final_state
