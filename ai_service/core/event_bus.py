from __future__ import annotations

import time
import uuid
import inspect
import logging
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Any, Mapping

logger = logging.getLogger(__name__)


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
