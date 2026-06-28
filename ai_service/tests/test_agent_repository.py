"""Tests for agent_repository module, focusing on _row_to_agent and SQL constants."""

from __future__ import annotations

from decimal import Decimal

import pytest

from repositories.agent_repository import (
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
