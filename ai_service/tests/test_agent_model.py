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
