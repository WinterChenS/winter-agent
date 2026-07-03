import pytest

from context.models import ContextRequest
from context.providers.session import SessionContextProvider


@pytest.mark.asyncio
async def test_collect_uses_recent_visible_messages(monkeypatch):
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "Thought: hidden internal step"},
        {"role": "assistant", "content": "这里是最终回答"},
    ]

    async def fake_loader(pool, conversation_id):
        return messages

    monkeypatch.setattr(
        "context.providers.session.get_messages_by_conversation",
        fake_loader,
    )
    provider = SessionContextProvider(pool=object(), history_limit=5)

    fragments = await provider.collect(
        ContextRequest("conv-1", "继续", "default", 200)
    )

    assert len(fragments) == 1
    assert "这里是最终回答" in fragments[0].content
    assert "Thought:" not in fragments[0].content


@pytest.mark.asyncio
async def test_collect_returns_empty_without_session_id():
    provider = SessionContextProvider(pool=None, history_limit=5)

    fragments = await provider.collect(ContextRequest(None, "hello", "default", 200))

    assert fragments == []