import pytest

from context.budget import estimate_text_tokens, trim_text_to_budget
from context.models import AgentContext, ContextFragment, ContextRequest
from context.providers.files import FileContextProvider
from context.providers.knowledge import KnowledgeContextProvider
from context.providers.memory import MemoryContextProvider


def test_context_request_and_fragment_defaults():
    request = ContextRequest(
        session_id="conv-1",
        user_query="hello",
        agent_id="default",
        max_tokens=400,
    )
    fragment = ContextFragment(
        provider="session",
        content="recent history",
        tokens=2,
        priority=10,
        metadata={"source": "db"},
    )
    context = AgentContext(
        session_id="conv-1",
        agent_id="default",
        recent_messages=[{"role": "user", "content": "hello"}],
        fragments=[fragment],
        rendered_prompt="recent history",
        token_usage={"session": 2},
        metadata={"providers": ["session"]},
    )

    assert request.max_tokens == 400
    assert context.fragments[0].provider == "session"
    assert context.metadata["providers"] == ["session"]


def test_budget_helpers_are_deterministic():
    assert estimate_text_tokens("alpha beta gamma") >= 3
    assert trim_text_to_budget("one two three four", max_tokens=2).split() == [
        "one",
        "two",
    ]


@pytest.mark.asyncio
async def test_stub_providers_share_contract_and_degrade():
    request = ContextRequest(
        session_id="conv-1",
        user_query="hello",
        agent_id="default",
        max_tokens=400,
    )

    providers = [
        (FileContextProvider(), "files", 20),
        (MemoryContextProvider(), "memory", 30),
        (KnowledgeContextProvider(), "knowledge", 40),
    ]

    for provider, name, priority in providers:
        assert provider.name == name
        assert provider.priority == priority
        assert await provider.collect(request) == []