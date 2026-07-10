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
