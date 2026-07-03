from context.models import ContextFragment, ContextRequest


class KnowledgeContextProvider:
    name = "knowledge"
    priority = 40

    async def collect(self, request: ContextRequest) -> list[ContextFragment]:
        return []