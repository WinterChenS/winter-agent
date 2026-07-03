import pytest
from core.agent_factory import AgentFactory, AgentRuntime
from models.agent import AgentDefinition
from tools.base import BaseTool, ToolResult


# Mock tool for testing
class _MockTool(BaseTool):
    name = "mock_tool"
    description = "A mock tool"
    input_schema = {}

    async def execute(self, input):
        return ToolResult.success({"result": "mock"})


def test_agent_factory_build(monkeypatch):
    # Mock ToolRegistry
    class MockRegistry:
        def get(self, name):
            return _MockTool() if name == "mock_tool" else None

    monkeypatch.setattr("core.agent_factory.get_tool_registry", lambda: MockRegistry())

    factory = AgentFactory()
    definition = AgentDefinition(
        name="test_agent",
        display_name="Test",
        system_prompt="You are {role}. Time: {current_time}.",
        tools=["mock_tool"],
        collaboration_strategy="parallel",
    )

    runtime = factory.build(definition, context={"role": "tester"})

    assert isinstance(runtime, AgentRuntime)
    assert runtime.name == "test_agent"
    assert runtime.strategy == "parallel"
    assert len(runtime.tools) == 1
    assert runtime.tools[0].name == "mock_tool"
    assert "tester" in runtime.system_prompt
    assert "current_time" not in runtime.system_prompt  # Should be replaced with actual time


def test_agent_factory_unknown_tool_skipped(monkeypatch):
    class MockRegistry:
        def get(self, name):
            raise Exception("tool not found")

    monkeypatch.setattr("core.agent_factory.get_tool_registry", lambda: MockRegistry())

    factory = AgentFactory()
    definition = AgentDefinition(
        name="test", display_name="T", system_prompt="Hi",
        tools=["nonexistent_tool"],
    )

    runtime = factory.build(definition)
    assert runtime.tools == []


def test_agent_factory_default_context(monkeypatch):
    monkeypatch.setattr("core.agent_factory.get_tool_registry", lambda: None)

    factory = AgentFactory()
    definition = AgentDefinition(name="test", display_name="T", system_prompt="Time is {current_time}")

    runtime = factory.build(definition)
    assert "current_time" not in runtime.system_prompt  # Replaced with datetime


def test_agent_factory_appends_runtime_context(monkeypatch):
    monkeypatch.setattr("core.agent_factory.get_tool_registry", lambda: None)

    factory = AgentFactory()
    definition = AgentDefinition(name="test", display_name="T", system_prompt="Base prompt")

    runtime = factory.build(definition, context={"runtime_context_prompt": "[session]\nuser: 历史"})

    assert "Base prompt" in runtime.system_prompt
    assert "[session]" in runtime.system_prompt
