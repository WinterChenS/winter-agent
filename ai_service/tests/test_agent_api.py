from __future__ import annotations

import pytest

from models.agent import AgentDefinition
from repositories.agent_repository import AgentRepository, MockAgentRepository


@pytest.fixture
def repo() -> AgentRepository:
    return MockAgentRepository()


@pytest.fixture
def sample_agent() -> AgentDefinition:
    return AgentDefinition(
        name="test", display_name="Test", system_prompt="Be helpful.",
        tools=["search"], trigger_keywords=["搜索"], collaboration_strategy="parallel",
    )


@pytest.mark.asyncio
async def test_create_and_list(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    assert created.name == "test"
    agents = await repo.list_all()
    assert len(agents) == 1


@pytest.mark.asyncio
async def test_get_by_id(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.name == "test"


@pytest.mark.asyncio
async def test_update(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    updated_agent = AgentDefinition(name="updated", display_name="Updated", system_prompt="New")
    result = await repo.update(created.id, updated_agent)
    assert result is not None
    assert result.name == "updated"


@pytest.mark.asyncio
async def test_delete(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    ok = await repo.delete(created.id)
    assert ok is True
    assert await repo.get_by_id(created.id) is None


@pytest.mark.asyncio
async def test_list_enabled(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    await repo.create(sample_agent)
    disabled = AgentDefinition(name="off", display_name="Off", system_prompt="...", enabled=False)
    await repo.create(disabled)
    agents = await repo.list_enabled()
    assert len(agents) == 1
    assert agents[0].name == "test"


@pytest.mark.asyncio
async def test_update_nonexistent_returns_none(repo: AgentRepository) -> None:
    agent = AgentDefinition(name="ghost", display_name="Ghost", system_prompt="...")
    result = await repo.update("nonexistent", agent)
    assert result is None


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_false(repo: AgentRepository) -> None:
    ok = await repo.delete("nonexistent")
    assert ok is False


@pytest.mark.asyncio
async def test_get_by_id_nonexistent_returns_none(repo: AgentRepository) -> None:
    found = await repo.get_by_id("nonexistent")
    assert found is None
