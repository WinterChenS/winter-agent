import pytest
from models.agent import AgentDefinition


def test_agent_definition_valid():
    agent = AgentDefinition(
        name="test_agent",
        display_name="Test Agent",
        description="A test agent",
        system_prompt="You are a helpful assistant.",
        tools=["search", "time"],
        model_params={"temperature": 0.7},
        trigger_keywords=["搜索", "测试"],
        collaboration_strategy="parallel",
        priority=1,
    )
    assert agent.name == "test_agent"
    assert agent.tools == ["search", "time"]


def test_agent_definition_defaults():
    agent = AgentDefinition(
        name="minimal",
        display_name="Minimal",
        system_prompt="Be helpful.",
    )
    assert agent.tools == []
    assert agent.model_params == {"temperature": 0.7}
    assert agent.collaboration_strategy == "sequential"
    assert agent.priority == 0
    assert agent.enabled is True


def test_invalid_collaboration_strategy():
    with pytest.raises(ValueError):
        AgentDefinition(
            name="bad",
            display_name="Bad",
            system_prompt="...",
            collaboration_strategy="invalid_strategy",
        )


def test_name_max_length():
    with pytest.raises(ValueError):
        AgentDefinition(
            name="a" * 65,
            display_name="Too Long Name",
            system_prompt="...",
        )


def test_agent_definition_new_fields_defaults():
    agent = AgentDefinition(
        name="new_fields",
        display_name="New Fields",
        system_prompt="Test.",
    )
    assert agent.icon == ""
    assert agent.agent_type == ""
    assert agent.avatar_url == ""
    assert agent.is_builtin is False
    assert agent.tags == []
    assert agent.metadata == {}
    assert agent.created_by == ""
    assert agent.updated_by == ""
    assert agent.version == 1


def test_agent_definition_new_fields_custom():
    agent = AgentDefinition(
        name="custom",
        display_name="Custom",
        system_prompt="Test.",
        icon="🤖",
        agent_type="assistant",
        avatar_url="https://example.com/avatar.png",
        is_builtin=True,
        tags=["ai", "chat"],
        metadata={"tier": "premium"},
        created_by="admin",
        updated_by="admin",
        version=3,
    )
    assert agent.icon == "🤖"
    assert agent.agent_type == "assistant"
    assert agent.tags == ["ai", "chat"]
    assert agent.metadata == {"tier": "premium"}
    assert agent.version == 3
