import pytest

from core.event_bus import EventBus, RuntimeEvent
from core.streaming_event_bus import StreamingEventBus


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


@pytest.mark.asyncio
async def test_event_bus_exact_topic_subscription():
    bus = EventBus()
    received = []

    async def handler(event: RuntimeEvent):
        received.append(event)

    bus.subscribe("tool.invoke", handler)
    event = RuntimeEvent.create(event_type="tool.invoke", source="test")

    await bus.publish(event)

    assert received == [event]


@pytest.mark.asyncio
async def test_event_bus_wildcard_subscription_matches_single_segment():
    bus = EventBus()
    received = []

    bus.subscribe("tool.*", lambda event: received.append(event.event_type))

    await bus.publish(RuntimeEvent.create(event_type="tool.invoke", source="test"))
    await bus.publish(RuntimeEvent.create(event_type="tool.result", source="test"))
    await bus.publish(RuntimeEvent.create(event_type="tool.sandbox.output", source="test"))

    assert received == ["tool.invoke", "tool.result"]


@pytest.mark.asyncio
async def test_event_bus_unsubscribe_stops_delivery():
    bus = EventBus()
    received = []

    subscription = bus.subscribe("graph.enter", lambda event: received.append(event))
    bus.unsubscribe(subscription.subscription_id)

    await bus.publish(RuntimeEvent.create(event_type="graph.enter", source="test"))

    assert received == []


@pytest.mark.asyncio
async def test_event_bus_publish_without_subscribers_succeeds():
    bus = EventBus()

    await bus.publish(RuntimeEvent.create(event_type="llm.request", source="test"))


@pytest.mark.asyncio
async def test_event_bus_subscriber_failure_does_not_stop_publish_or_other_handlers():
    bus = EventBus()
    received = []

    async def bad_handler(event: RuntimeEvent):
        raise RuntimeError("boom")

    async def good_handler(event: RuntimeEvent):
        received.append(event.event_type)

    bus.subscribe("tool.*", bad_handler)
    bus.subscribe("tool.*", good_handler)

    await bus.publish(RuntimeEvent.create(event_type="tool.invoke", source="test"))

    assert received == ["tool.invoke"]


@pytest.mark.asyncio
async def test_event_bus_instances_are_isolated_for_request_scope():
    first_bus = EventBus()
    second_bus = EventBus()
    first_received = []
    second_received = []

    first_bus.subscribe("message.delta", lambda event: first_received.append(event.event_id))
    second_bus.subscribe("message.delta", lambda event: second_received.append(event.event_id))

    event = RuntimeEvent.create(event_type="message.delta", source="request-1", event_id="evt-1")
    await first_bus.publish(event)

    assert first_received == ["evt-1"]
    assert second_received == []


@pytest.mark.asyncio
async def test_streaming_event_bus_legacy_emit_events_and_close():
    bus = StreamingEventBus()
    bus.emit("tool.started", toolName="search")

    events = bus.events()
    event = await events.__anext__()
    assert event.type == "tool.started"
    assert event.data == {"toolName": "search"}

    bus.close()
    with pytest.raises(StopAsyncIteration):
        await events.__anext__()
