from context.models import ContextFragment, ContextRequest


class MemoryContextProvider:
    name = "memory"
    priority = 30

    async def collect(self, request: ContextRequest) -> list[ContextFragment]:
        return []