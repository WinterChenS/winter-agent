from __future__ import annotations

from typing import Protocol

from context.models import ContextFragment, ContextRequest


class ContextProvider(Protocol):
    name: str
    priority: int

    async def collect(self, request: ContextRequest) -> list[ContextFragment]:
        ...