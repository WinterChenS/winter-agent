import pytest

from context.builder import ContextBuilder
from context.models import ContextFragment, ContextRequest


class _Provider:
    def __init__(self, name, priority, fragments):
        self.name = name
        self.priority = priority
        self._fragments = fragments

    async def collect(self, request):
        return self._fragments


@pytest.mark.asyncio
async def test_builder_keeps_high_priority_fragments_when_budget_tight():
    request = ContextRequest("conv-1", "hello", "default", 4)
    session = ContextFragment("session", "one two three", 3, 10, {"recent_messages": []})
    files = ContextFragment("files", "four five six", 3, 20, {})

    builder = ContextBuilder(
        [_Provider("session", 10, [session]), _Provider("files", 20, [files])]
    )
    context = await builder.build(request)

    assert "one two three" in context.rendered_prompt
    assert "four five six" not in context.rendered_prompt


@pytest.mark.asyncio
async def test_builder_returns_empty_context_when_all_providers_empty():
    builder = ContextBuilder([_Provider("session", 10, [])])

    context = await builder.build(ContextRequest(None, "hello", None, 50))

    assert context.rendered_prompt == ""
    assert context.fragments == []