from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class StreamingEvent:
    """A progress event pushed from inside graph nodes to the SSE stream."""
    type: str
    data: dict[str, Any]
    timestamp: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = int(time.time() * 1000)


class StreamingEventBus:
    """asyncio.Queue-based side channel for real-time SSE events from inside LangGraph nodes."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[StreamingEvent | None] = asyncio.Queue()

    def emit(self, event_type: str, **data: Any) -> None:
        """Publish an event. Called from inside graph nodes.

        Uses ``put_nowait`` to avoid blocking the caller, then schedules a
        no-op callback to prompt the event loop to wake bus_runner promptly
        rather than deferring until the next await in the calling coroutine.
        """
        self._queue.put_nowait(StreamingEvent(type=event_type, data=data))
        asyncio.get_event_loop().call_soon(lambda: None)

    async def events(self):
        """Async generator yielding events. Called from the SSE event loop."""
        while True:
            event = await self._queue.get()
            if event is None:  # sentinel to stop
                break
            yield event

    def close(self) -> None:
        """Signal the generator to stop."""
        self._queue.put_nowait(None)
