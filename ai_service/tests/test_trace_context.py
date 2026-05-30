from observability.trace import ensure_trace_context, new_span


def test_trace_created_per_turn():
    first = ensure_trace_context("conv-abc")
    second = ensure_trace_context("conv-abc")

    assert first.conversation_id == "conv-abc"
    assert second.conversation_id == "conv-abc"
    assert first.turn_id != second.turn_id
    assert first.trace_id != second.trace_id


def test_tool_span_parent_is_agent_span():
    ctx = ensure_trace_context("conv-xyz")
    tool_span = new_span(ctx.span_id, name="tool:search")

    assert tool_span.startswith("spn_")
    assert tool_span != ctx.span_id

