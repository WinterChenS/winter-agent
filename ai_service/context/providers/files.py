from context.models import ContextFragment, ContextRequest


class FileContextProvider:
    name = "files"
    priority = 20

    async def collect(self, request: ContextRequest) -> list[ContextFragment]:
        return []