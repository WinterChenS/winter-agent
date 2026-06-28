"""Tests for agent_repository module, focusing on _row_to_agent and SQL constants."""

from __future__ import annotations

import datetime

from decimal import Decimal

import pytest

from models.agent import AgentDefinition
from repositories.agent_repository import (
    AgentRepository,
    MockAgentRepository,
    _AGENT_COLS,
    _AGENT_SELECT,
    _row_to_agent,
)


def test_agent_select_column_count_matches_cols():
    """The number of columns in _AGENT_SELECT must match _AGENT_COLS length."""
    select_line = _AGENT_SELECT.strip().removeprefix("SELECT").split("FROM")[0]
    columns_in_select = [c.strip() for c in select_line.split(",")]
    assert len(columns_in_select) == len(_AGENT_COLS), (
        f"_AGENT_SELECT has {len(columns_in_select)} columns but "
        f"_AGENT_COLS has {len(_AGENT_COLS)} entries"
    )


def test_row_to_agent_new_fields():
    """_row_to_agent must correctly extract the 9 new fields from a full DB row."""
    row = (
        "agent-001",                          # id
        "test_agent",                          # name
        "Test Agent",                          # display_name
        "A test agent",                        # description
        "You are helpful.",                    # system_prompt
        '["tool1","tool2"]',                   # tools (JSON)
        '{"temperature":0.5}',                 # model_config (JSON)
        '["kw1","kw2"]',                       # trigger_keywords (JSON)
        "parallel",                            # collaboration_strategy
        Decimal("3"),                          # priority
        True,                                  # enabled
        datetime.datetime(2026, 6, 28, 0, 0),  # created_at
        datetime.datetime(2026, 6, 28, 0, 0),  # updated_at
        "robot",                               # icon
        "assistant",                           # agent_type
        "https://example.com/avatar.png",      # avatar_url
        True,                                  # is_builtin
        '["ai","chat"]',                       # tags (JSON)
        '{"tier":"premium","env":"prod"}',     # metadata (JSON)
        "admin",                               # created_by
        "admin",                               # updated_by
        3,                                     # version
    )
    agent = _row_to_agent(row)

    # Original fields still work
    assert agent.id == "agent-001"
    assert agent.name == "test_agent"
    assert agent.tools == ["tool1", "tool2"]
    assert agent.model_params == {"temperature": 0.5}
    assert agent.trigger_keywords == ["kw1", "kw2"]

    # --- 9 new fields ---
    assert agent.icon == "robot", f"Expected icon='robot', got {agent.icon!r}"
    assert agent.agent_type == "assistant"
    assert agent.avatar_url == "https://example.com/avatar.png"
    assert agent.is_builtin is True
    assert agent.tags == ["ai", "chat"]
    assert agent.metadata == {"tier": "premium", "env": "prod"}
    assert agent.created_by == "admin"
    assert agent.updated_by == "admin"
    assert agent.version == 3


def test_row_to_agent_new_fields_defaults():
    """_row_to_agent should use defaults when new fields are NULL in DB."""
    row = (
        "agent-002",                          # id
        "minimal",                             # name
        "Minimal",                             # display_name
        "",                                    # description
        "Be helpful.",                         # system_prompt
        "[]",                                  # tools (JSON)
        '{"temperature":0.7}',                 # model_config (JSON)
        "[]",                                  # trigger_keywords (JSON)
        "sequential",                          # collaboration_strategy
        Decimal("0"),                          # priority
        True,                                  # enabled
        datetime.datetime(2026, 6, 28, 0, 0),  # created_at
        datetime.datetime(2026, 6, 28, 0, 0),  # updated_at
        None,                                  # icon
        None,                                  # agent_type
        None,                                  # avatar_url
        None,                                  # is_builtin
        None,                                  # tags (JSON NULL)
        None,                                  # metadata (JSON NULL)
        None,                                  # created_by
        None,                                  # updated_by
        None,                                  # version
    )
    agent = _row_to_agent(row)

    assert agent.icon == ""
    assert agent.agent_type == ""
    assert agent.avatar_url == ""
    assert agent.is_builtin is False
    assert agent.tags == []
    assert agent.metadata == {}
    assert agent.created_by == ""
    assert agent.updated_by == ""
    assert agent.version == 1


def test_row_to_agent_json_deserialization():
    """Verify JSON deserialization for all 5 JSON fields (tools, model_config, trigger_keywords, tags, metadata)."""
    row = (
        "agent-003",                          # id
        "json_test",                           # name
        "JSON Test",                           # display_name
        "",                                    # description
        "Test.",                               # system_prompt
        '["a","b"]',                           # tools (JSON)
        '{"temp":0.3,"model":"gpt-4"}',        # model_config (JSON)
        '["x","y"]',                           # trigger_keywords (JSON)
        "sequential",                          # collaboration_strategy
        Decimal("0"),                          # priority
        True,                                  # enabled
        datetime.datetime(2026, 6, 28, 0, 0),  # created_at
        datetime.datetime(2026, 6, 28, 0, 0),  # updated_at
        None,                                  # icon
        None,                                  # agent_type
        None,                                  # avatar_url
        None,                                  # is_builtin
        '["tag1","tag2"]',                     # tags (JSON)
        '{"key":"value"}',                     # metadata (JSON)
        None,                                  # created_by
        None,                                  # updated_by
        None,                                  # version
    )
    agent = _row_to_agent(row)

    assert agent.tools == ["a", "b"]
    assert agent.model_params == {"temp": 0.3, "model": "gpt-4"}
    assert agent.trigger_keywords == ["x", "y"]
    assert agent.tags == ["tag1", "tag2"]
    assert agent.metadata == {"key": "value"}


@pytest.mark.asyncio
async def test_set_enabled_disables_agent() -> None:
    """MockAgentRepository.set_enabled must disable an agent when enabled=False."""
    repo: AgentRepository = MockAgentRepository()
    agent = AgentDefinition(
        id="test-disable-001",
        name="disable-me",
        display_name="Disable Me",
        description="To be disabled",
        system_prompt="You will be disabled.",
    )
    await repo.create(agent)

    result = await repo.set_enabled("test-disable-001", False)

    assert result is not None
    assert result.id == "test-disable-001"
    assert result.enabled is False

    stored = await repo.get_by_id("test-disable-001")
    assert stored is not None
    assert stored.enabled is False


@pytest.mark.asyncio
async def test_set_enabled_enables_agent() -> None:
    """MockAgentRepository.set_enabled must enable an agent when enabled=True."""
    repo: AgentRepository = MockAgentRepository()
    agent = AgentDefinition(
        id="test-enable-001",
        name="enable-me",
        display_name="Enable Me",
        description="To be enabled",
        system_prompt="You will be enabled.",
        enabled=False,
    )
    await repo.create(agent)

    result = await repo.set_enabled("test-enable-001", True)

    assert result is not None
    assert result.id == "test-enable-001"
    assert result.enabled is True

    stored = await repo.get_by_id("test-enable-001")
    assert stored is not None
    assert stored.enabled is True


@pytest.mark.asyncio
async def test_set_enabled_returns_none_when_not_found() -> None:
    """MockAgentRepository.set_enabled must return None for non-existent agent_id."""
    repo: AgentRepository = MockAgentRepository()

    result = await repo.set_enabled("non-existent-id", False)

    assert result is None


# ── clone tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clone_returns_none_when_not_found() -> None:
    """clone must return None when the source agent does not exist."""
    repo: AgentRepository = MockAgentRepository()

    result = await repo.clone("non-existent-id")

    assert result is None


@pytest.mark.asyncio
async def test_clone_basic() -> None:
    """clone a basic agent and verify name, display_name, version, is_builtin, created_by."""
    repo: AgentRepository = MockAgentRepository()
    agent = AgentDefinition(
        id="clone-src-001",
        name="my-agent",
        display_name="My Agent",
        description="Original agent",
        system_prompt="You are helpful.",
        is_builtin=True,
        version=5,
        created_by="admin",
    )
    await repo.create(agent)

    cloned = await repo.clone("clone-src-001", created_by="winter")

    assert cloned is not None
    assert cloned.id != "clone-src-001"
    assert cloned.name == "my-agent-copy"
    assert cloned.display_name == "My Agent (Copy)"
    assert cloned.version == 1
    assert cloned.is_builtin is False
    assert cloned.created_by == "winter"
    assert cloned.description == "Original agent"
    assert cloned.system_prompt == "You are helpful."


@pytest.mark.asyncio
async def test_clone_generates_new_id() -> None:
    """clone must generate a different id from the source."""
    repo: AgentRepository = MockAgentRepository()
    agent = AgentDefinition(
        id="clone-src-002",
        name="another-agent",
        display_name="Another Agent",
        system_prompt="Test.",
    )
    await repo.create(agent)

    cloned = await repo.clone("clone-src-002")

    assert cloned is not None
    assert cloned.id != "clone-src-002"
    assert len(cloned.id) == 12  # uuid hex[:12]


@pytest.mark.asyncio
async def test_clone_copies_all_fields() -> None:
    """clone must copy tools, model_config, trigger_keywords, collaboration_strategy, priority, etc."""
    repo: AgentRepository = MockAgentRepository()
    agent = AgentDefinition(
        id="clone-src-003",
        name="rich-agent",
        display_name="Rich Agent",
        description="Has many fields",
        system_prompt="You are rich.",
        tools=["tool1", "tool2"],
        model_config={"temperature": 0.8, "model": "gpt-4"},
        trigger_keywords=["hello", "hi"],
        collaboration_strategy="parallel",
        priority=10,
        enabled=True,
        icon="robot",
        agent_type="assistant",
        avatar_url="https://example.com/avatar.png",
        tags=["ai", "chat"],
        metadata={"tier": "premium"},
    )
    await repo.create(agent)

    cloned = await repo.clone("clone-src-003")

    assert cloned is not None
    assert cloned.tools == ["tool1", "tool2"]
    assert cloned.model_params == {"temperature": 0.8, "model": "gpt-4"}
    assert cloned.trigger_keywords == ["hello", "hi"]
    assert cloned.collaboration_strategy == "parallel"
    assert cloned.priority == 10
    assert cloned.enabled is True
    assert cloned.icon == "robot"
    assert cloned.agent_type == "assistant"
    assert cloned.avatar_url == "https://example.com/avatar.png"
    assert cloned.tags == ["ai", "chat"]
    assert cloned.metadata == {"tier": "premium"}


@pytest.mark.asyncio
async def test_clone_name_already_copy() -> None:
    """clone must append numeric suffix when source name already ends with -copy."""
    repo: AgentRepository = MockAgentRepository()
    agent = AgentDefinition(
        id="clone-src-004",
        name="my-agent-copy",
        display_name="My Agent",
        system_prompt="Copy of something.",
    )
    await repo.create(agent)

    cloned = await repo.clone("clone-src-004")

    assert cloned is not None
    assert cloned.name == "my-agent-copy2"


@pytest.mark.asyncio
async def test_clone_name_already_copy_with_number() -> None:
    """clone must increment numeric suffix when source name already ends with -copyN."""
    repo: AgentRepository = MockAgentRepository()
    agent = AgentDefinition(
        id="clone-src-005",
        name="my-agent-copy3",
        display_name="My Agent",
        system_prompt="Third copy.",
    )
    await repo.create(agent)

    cloned = await repo.clone("clone-src-005")

    assert cloned is not None
    assert cloned.name == "my-agent-copy4"


@pytest.mark.asyncio
async def test_clone_name_copy_with_number_ten() -> None:
    """clone must handle double-digit numeric suffixes correctly."""
    repo: AgentRepository = MockAgentRepository()
    agent = AgentDefinition(
        id="clone-src-006",
        name="my-agent-copy9",
        display_name="My Agent",
        system_prompt="Ninth copy.",
    )
    await repo.create(agent)

    cloned = await repo.clone("clone-src-006")

    assert cloned is not None
    assert cloned.name == "my-agent-copy10"


@pytest.mark.asyncio
async def test_clone_persists_in_repo() -> None:
    """clone must store the cloned agent in the repository."""
    repo: AgentRepository = MockAgentRepository()
    agent = AgentDefinition(
        id="clone-src-007",
        name="persist-me",
        display_name="Persist Me",
        system_prompt="I will be cloned.",
    )
    await repo.create(agent)

    cloned = await repo.clone("clone-src-007")

    assert cloned is not None
    # Verify it's stored and retrievable
    stored = await repo.get_by_id(cloned.id)
    assert stored is not None
    assert stored.name == "persist-me-copy"
    assert stored.display_name == "Persist Me (Copy)"
    assert stored.version == 1
