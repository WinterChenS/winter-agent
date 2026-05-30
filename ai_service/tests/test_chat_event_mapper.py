from api.events.event_mapper import (
    EventMapContext,
    emit_guard_reason_envelope,
    emit_final_summary_envelope,
    map_langgraph_event_to_envelopes,
    process_stream_token_event,
)
from observability.trace import ensure_trace_context


class _Chunk:
    def __init__(self, content: str):
        self.content = content


def _ctx() -> EventMapContext:
    return EventMapContext(trace_ctx=ensure_trace_context("conv-map"), known_tools={"search", "time"})


def test_map_chat_model_stream_to_token():
    event = {"event": "on_chat_model_stream", "data": {"chunk": _Chunk("hello")}}
    mapped, span, final_state = map_langgraph_event_to_envelopes(event, _ctx(), None)

    assert span is None
    assert final_state is None
    assert len(mapped) == 1
    assert mapped[0]["type"] == "token"
    assert mapped[0]["content"] == "hello"


def test_map_tool_start_event():
    event = {"event": "on_chain_start", "name": "tool", "data": {"input": {"current_tool": "search"}}}
    mapped, span, final_state = map_langgraph_event_to_envelopes(event, _ctx(), None)

    assert final_state is None
    assert span is not None
    assert len(mapped) == 1
    assert mapped[0]["type"] == "tool_start"
    assert mapped[0]["toolName"] == "search"


def test_map_tool_end_event():
    event = {
        "event": "on_chain_end",
        "name": "tool",
        "data": {
            "input": {"current_tool": "search"},
            "output": {
                "current_tool": "search",
                "tool_result": '{"ok": true, "data": {"query": "q", "results": []}}',
            },
        },
    }
    mapped, span, final_state = map_langgraph_event_to_envelopes(event, _ctx(), "spn_prev")

    assert final_state is None
    assert span is None
    assert len(mapped) == 1
    assert mapped[0]["type"] == "tool_result"
    assert mapped[0]["toolName"] == "search"


def test_emit_tool_summary_from_final_state():
    ctx = _ctx()
    final_state = {"tool_steps": [{"tool": "search", "status": "completed"}]}
    envelope = emit_final_summary_envelope(final_state, ctx)

    assert envelope is not None
    assert envelope["type"] == "tool_summary"
    assert envelope["payload"]["steps"][0]["tool"] == "search"


def test_process_stream_token_event_buffers_partial_control_json():
    event = {"event": "on_chat_model_stream", "data": {"chunk": _Chunk('{"action": "tool"')}}
    rewritten, collecting, buffer, preamble, thought = process_stream_token_event(event, False, "", {"search", "time"})

    assert rewritten is None
    assert collecting is True
    assert buffer.startswith('{"action"')


def test_process_stream_token_event_filters_tool_control_json():
    part1 = {"event": "on_chat_model_stream", "data": {"chunk": _Chunk('{"action": "tool",')}}
    _ , collecting, buffer, preamble, thought = process_stream_token_event(part1, False, "", {"search", "time"})

    part2 = {"event": "on_chat_model_stream", "data": {"chunk": _Chunk('"tool": "search", "query": "x"}')}}
    rewritten, collecting, buffer, preamble, thought = process_stream_token_event(part2, collecting, buffer, {"search", "time"})

    assert rewritten is None
    assert collecting is False
    assert buffer == ""


def test_process_stream_token_event_keeps_normal_json_text():
    event = {"event": "on_chat_model_stream", "data": {"chunk": _Chunk('{"note": "hello"}')}}
    rewritten, collecting, buffer, preamble, thought = process_stream_token_event(event, False, "", {"search", "time"})

    assert rewritten is not None
    assert collecting is False
    assert buffer == ""


def test_emit_tool_summary_returns_none_for_empty_steps():
    envelope = emit_final_summary_envelope({"tool_steps": []}, _ctx())
    assert envelope is None


def test_emit_guard_reason_envelope_from_final_state():
    envelope = emit_guard_reason_envelope(
        {"last_guard_reason": {"code": "MAX_CONSECUTIVE_SEARCH_REACHED", "message": "guard"}},
        _ctx(),
    )
    assert envelope is not None
    assert envelope["type"] == "agent_step"
    assert envelope["payload"]["reason"]["code"] == "MAX_CONSECUTIVE_SEARCH_REACHED"


def test_emit_guard_reason_returns_none_when_absent():
    envelope = emit_guard_reason_envelope({"last_guard_reason": None}, _ctx())
    assert envelope is None


