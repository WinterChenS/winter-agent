---
change: agent-runtime-event-bus-core
design-doc: docs/superpowers/specs/2026-07-10-agent-runtime-event-bus-core-design.md
base-ref: 87d362c155bbe140b51b687ea6aebb53eff3f0a7
---

# Agent Runtime Event Bus Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a request-scoped, in-process Runtime Event Bus core for AI service without adding external infrastructure.

**Architecture:** Add a focused `ai_service/core/event_bus.py` module containing `RuntimeEvent`, `Subscription`, and `EventBus`. Keep existing `StreamingEventBus` behavior intact for this change; prove compatibility with tests instead of migrating SSE wiring now.

**Tech Stack:** Python 3.12, dataclasses, asyncio, pytest, existing AI service package layout.

## Global Constraints

- Do not add Redis, RabbitMQ, Kafka, or any new external message component.
- `EventBus` must be a normal instantiable object, not a mandatory global singleton.
- Default runtime usage is request-scoped: separate chat requests use separate EventBus instances.
- Topic matching supports exact matches and single-segment `*` only.
- Subscriber failures must not propagate to the runtime publish caller.
- This change does not wire LLM, Tool, Graph, SSE, or persistence integrations.

---

## File Structure

- Create `ai_service/core/event_bus.py`
  - Owns `RuntimeEvent`, `Subscription`, `EventBus`, topic matching, handler dispatch, serialization helpers.
- Create `ai_service/tests/test_event_bus.py`
  - Covers the new runtime event model and event bus behavior.
- Modify `ai_service/tests/test_event_bus.py`
  - Add compatibility tests for existing `StreamingEventBus`; keep them in the same file because they validate the event-bus boundary.
- Modify `openspec/changes/agent-runtime-event-bus-core/tasks.md`
  - Check off tasks only after the corresponding tests pass.

### Task 1: RuntimeEvent Model

**Files:**
- Create: `ai_service/core/event_bus.py`
- Create: `ai_service/tests/test_event_bus.py`

**Interfaces:**
- Produces: `RuntimeEvent.create(event_type: str, source: str, trace_id: str = "", span_id: str = "", payload: Mapping[str, Any] | None = None, metadata: Mapping[str, Any] | None = None, event_id: str | None = None, timestamp: int | None = None) -> RuntimeEvent`
- Produces: `RuntimeEvent.to_dict() -> dict[str, Any]`

- [x] **Step 1: Write failing RuntimeEvent tests**

Add `ai_service/tests/test_event_bus.py`:

```python
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
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd ai_service && pytest tests/test_event_bus.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'core.event_bus'`.

- [x] **Step 3: Implement RuntimeEvent**

Create `ai_service/core/event_bus.py`:

```python
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    event_id: str
    event_type: str
    timestamp: int
    source: str
    trace_id: str
    span_id: str
    payload: dict[str, Any]
    metadata: dict[str, Any]

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        source: str,
        trace_id: str = "",
        span_id: str = "",
        payload: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        event_id: str | None = None,
        timestamp: int | None = None,
    ) -> "RuntimeEvent":
        return cls(
            event_id=event_id or str(uuid.uuid4()),
            event_type=event_type,
            timestamp=timestamp if timestamp is not None else int(time.time() * 1000),
            source=source,
            trace_id=trace_id,
            span_id=span_id,
            payload=dict(payload or {}),
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "source": self.source,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "payload": self.payload,
            "metadata": self.metadata,
        }
```

- [x] **Step 4: Run RuntimeEvent tests**

Run: `cd ai_service && pytest tests/test_event_bus.py -q`

Expected: PASS for the two RuntimeEvent tests.

- [x] **Step 5: Mark OpenSpec tasks and commit**

Update `openspec/changes/agent-runtime-event-bus-core/tasks.md`:

```markdown
- [x] 1.1 Add a `RuntimeEvent` model with event ID, event type, timestamp, source, trace/span IDs, payload, and metadata.
- [x] 1.2 Add helpers for creating events with default timestamp, generated ID, and empty metadata.
- [x] 1.3 Add unit tests for required fields, default values, and serialization.
```

Commit:

```bash
git add ai_service/core/event_bus.py ai_service/tests/test_event_bus.py openspec/changes/agent-runtime-event-bus-core/tasks.md
git commit -m "feat: add runtime event model"
```

### Task 2: EventBus Publish and Subscription Core

**Files:**
- Modify: `ai_service/core/event_bus.py`
- Modify: `ai_service/tests/test_event_bus.py`

**Interfaces:**
- Consumes: `RuntimeEvent`
- Produces: `Subscription(subscription_id: str, topic: str, handler: EventHandler)`
- Produces: `EventBus.subscribe(topic: str, handler: EventHandler) -> Subscription`
- Produces: `EventBus.unsubscribe(subscription_id: str) -> None`
- Produces: `EventBus.publish(event: RuntimeEvent) -> None`

- [x] **Step 1: Write failing EventBus tests**

Append to `ai_service/tests/test_event_bus.py`:

```python
import pytest

from core.event_bus import EventBus, RuntimeEvent


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
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd ai_service && pytest tests/test_event_bus.py -q`

Expected: FAIL with `ImportError` or `AttributeError` for missing `EventBus`.

- [x] **Step 3: Implement Subscription, EventBus, and topic matching**

Extend `ai_service/core/event_bus.py`:

```python
import inspect
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

EventHandler = Callable[[RuntimeEvent], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class Subscription:
    subscription_id: str
    topic: str
    handler: EventHandler


class EventBus:
    """In-process event bus.

    The bus is intentionally instantiable and request-scoped by default.
    It does not depend on Redis, RabbitMQ, Kafka, or any external broker.
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, Subscription] = {}

    def subscribe(self, topic: str, handler: EventHandler) -> Subscription:
        subscription = Subscription(
            subscription_id=str(uuid.uuid4()),
            topic=topic,
            handler=handler,
        )
        self._subscriptions[subscription.subscription_id] = subscription
        return subscription

    def unsubscribe(self, subscription_id: str) -> None:
        self._subscriptions.pop(subscription_id, None)

    async def publish(self, event: RuntimeEvent) -> None:
        for subscription in list(self._subscriptions.values()):
            if not _topic_matches(subscription.topic, event.event_type):
                continue
            try:
                result = subscription.handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception(
                    "EventBus subscriber failed: subscription_id=%s topic=%s event_type=%s",
                    subscription.subscription_id,
                    subscription.topic,
                    event.event_type,
                )


def _topic_matches(pattern: str, event_type: str) -> bool:
    if pattern == event_type:
        return True
    pattern_parts = pattern.split(".")
    event_parts = event_type.split(".")
    if len(pattern_parts) != len(event_parts):
        return False
    return all(p == "*" or p == e for p, e in zip(pattern_parts, event_parts))
```

- [x] **Step 4: Run EventBus tests**

Run: `cd ai_service && pytest tests/test_event_bus.py -q`

Expected: PASS for RuntimeEvent and EventBus subscription tests.

- [x] **Step 5: Mark OpenSpec tasks and commit**

Update `openspec/changes/agent-runtime-event-bus-core/tasks.md`:

```markdown
- [x] 2.1 Implement in-process Event Bus publish, subscribe, and unsubscribe APIs.
- [x] 2.2 Implement exact topic matching and single-segment wildcard matching.
```

Commit:

```bash
git add ai_service/core/event_bus.py ai_service/tests/test_event_bus.py openspec/changes/agent-runtime-event-bus-core/tasks.md
git commit -m "feat: add in-process event bus"
```

### Task 3: Failure Isolation, Request Scope, and Compatibility Verification

**Files:**
- Modify: `ai_service/core/event_bus.py`
- Modify: `ai_service/tests/test_event_bus.py`
- Modify: `openspec/changes/agent-runtime-event-bus-core/tasks.md`

**Interfaces:**
- Consumes: `EventBus.publish`
- Consumes: existing `StreamingEventBus`
- Produces: verified request-scoped isolation and compatibility behavior.

- [x] **Step 1: Write failing failure-isolation and request-scoped tests**

Append to `ai_service/tests/test_event_bus.py`:

```python
from core.streaming_event_bus import StreamingEventBus


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
```

- [x] **Step 2: Run tests to verify current behavior**

Run: `cd ai_service && pytest tests/test_event_bus.py -q`

Expected: PASS if Task 2 already catches handler exceptions; if failure isolation was missed, FAIL on `test_event_bus_subscriber_failure_does_not_stop_publish_or_other_handlers`.

- [x] **Step 3: Fix failure isolation if needed**

If the failure isolation test fails, update `EventBus.publish()` so each handler call is wrapped in its own `try/except Exception` and uses `logger.exception(...)` exactly once per failed handler. Do not re-raise.

- [x] **Step 4: Run targeted compatibility tests**

Run:

```bash
cd ai_service && pytest tests/test_event_bus.py tests/test_parallel_protocol.py tests/test_code_sandbox.py -q
```

Expected: PASS. If `test_code_sandbox.py` requires optional environment setup and fails for unrelated external-service reasons, record the exact failure and still run `pytest tests/test_event_bus.py tests/test_parallel_protocol.py -q`.

- [x] **Step 5: Run OpenSpec validation**

Run:

```bash
/Users/winterchen/.nvm/versions/node/v22.14.0/bin/node /Users/winterchen/.nvm/versions/node/v22.14.0/lib/node_modules/@fission-ai/openspec/bin/openspec.js validate agent-runtime-event-bus-core --strict
```

Expected: PASS.

- [x] **Step 6: Mark remaining OpenSpec tasks and commit**

Update `openspec/changes/agent-runtime-event-bus-core/tasks.md`:

```markdown
- [x] 2.3 Ensure subscriber failures are isolated from publish callers.
- [x] 2.4 Add tests for exact subscriptions, wildcard subscriptions, no-subscriber publish, unsubscribe, and handler failure.
- [x] 3.1 Add a compatibility path or adapter for existing `StreamingEventBus` usage.
- [x] 3.2 Document the no-external-component constraint in code comments or module docs where the bus implementation is introduced.
- [x] 3.3 Verify existing tests for streaming event behavior still pass.
- [x] 4.1 Run targeted AI service tests for event bus and streaming compatibility.
- [x] 4.2 Run OpenSpec validation for `agent-runtime-event-bus-core`.
```

Commit:

```bash
git add ai_service/core/event_bus.py ai_service/tests/test_event_bus.py openspec/changes/agent-runtime-event-bus-core/tasks.md
git commit -m "test: verify event bus isolation and compatibility"
```

## Plan Self-Review

- Spec coverage: RuntimeEvent model is Task 1; in-process bus, publish/subscribe, wildcard, and no-subscriber behavior are Task 2; failure isolation, request-scoped isolation, and StreamingEventBus compatibility are Task 3.
- Placeholder scan: no placeholder markers or incomplete instruction text remain.
- Type consistency: `RuntimeEvent`, `Subscription`, `EventBus`, and `EventHandler` names are introduced before use and stay consistent across tasks.
