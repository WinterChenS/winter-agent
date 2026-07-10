from core.event_bus import RuntimeEvent


def test_runtime_event_create_fills_defaults():
    event = RuntimeEvent.create(
        event_type="tool.invoke",
        source="tool-registry",
        trace_id="trace-1",
        span_id="span-1",
        payload={"tool": "search"},
    )

    assert event.event_id
    assert event.event_type == "tool.invoke"
    assert event.source == "tool-registry"
    assert event.trace_id == "trace-1"
    assert event.span_id == "span-1"
    assert event.payload == {"tool": "search"}
    assert event.metadata == {}
    assert isinstance(event.timestamp, int)


def test_runtime_event_to_dict_preserves_fields():
    event = RuntimeEvent.create(
        event_type="graph.enter",
        source="graph",
        trace_id="trace-1",
        span_id="span-1",
        payload={"node": "planning"},
        metadata={"conversation_id": "conv-1"},
        event_id="evt-1",
        timestamp=1234567890000,
    )

    assert event.to_dict() == {
        "event_id": "evt-1",
        "event_type": "graph.enter",
        "timestamp": 1234567890000,
        "source": "graph",
        "trace_id": "trace-1",
        "span_id": "span-1",
        "payload": {"node": "planning"},
        "metadata": {"conversation_id": "conv-1"},
    }
