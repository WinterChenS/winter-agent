from __future__ import annotations

import pytest
from core.collaboration import CollaborationEngine, CollaborationResult
from core.agent_factory import AgentRuntime


class MockLLM:
    def __init__(self, response: str):
        self.response = response

    async def ainvoke(self, messages):
        return type("Response", (), {"content": self.response})()


@pytest.mark.asyncio
async def test_sequential_two_agents():
    runtime_a = AgentRuntime(
        name="agent_a",
        llm=MockLLM("Result from A: found 5 items"),
        system_prompt="You are agent A",
        tools=[],
        strategy="sequential",
    )
    runtime_b = AgentRuntime(
        name="agent_b",
        llm=MockLLM("Result from B: analyzed items, average is 42"),
        system_prompt="You are agent B",
        tools=[],
        strategy="sequential",
    )

    engine = CollaborationEngine()
    result = await engine.execute([runtime_a, runtime_b], "Find and analyze items", "sequential")

    assert result.content == "Result from B: analyzed items, average is 42"
    assert len(result.agent_results) == 2
    assert result.agent_results[0]["agent"] == "agent_a"
    assert result.agent_results[0]["status"] == "ok"
    assert result.agent_results[1]["agent"] == "agent_b"
    assert result.agent_results[1]["status"] == "ok"
    # Verify context passed: B's messages should include A's result
    assert "5 items" in result.agent_results[0]["output"]


@pytest.mark.asyncio
async def test_sequential_error_handling():
    class ErrorLLM:
        async def ainvoke(self, messages):
            raise Exception("LLM error")

    runtime_a = AgentRuntime(name="a", llm=ErrorLLM(), system_prompt="", tools=[], strategy="sequential")
    runtime_b = AgentRuntime(name="b", llm=MockLLM("ok"), system_prompt="", tools=[], strategy="sequential")

    engine = CollaborationEngine()
    result = await engine.execute([runtime_a, runtime_b], "test", "sequential")

    # Should break on error
    assert result.agent_results[0]["status"] == "error"
    assert len(result.agent_results) == 1  # B should not have executed


@pytest.mark.asyncio
async def test_sequential_single_agent():
    runtime = AgentRuntime(name="solo", llm=MockLLM("Done"), system_prompt="", tools=[], strategy="sequential")

    engine = CollaborationEngine()
    result = await engine.execute([runtime], "test", "sequential")

    assert result.content == "Done"
    assert len(result.agent_results) == 1


@pytest.mark.asyncio
async def test_parallel_two_agents():
    runtime_a = AgentRuntime(name="a", llm=MockLLM("Result A"), system_prompt="", tools=[], strategy="parallel")
    runtime_b = AgentRuntime(name="b", llm=MockLLM("Result B"), system_prompt="", tools=[], strategy="parallel")

    engine = CollaborationEngine()
    result = await engine.execute([runtime_a, runtime_b], "query", "parallel")

    assert len(result.agent_results) == 2
    assert "Result A" in result.content
    assert "Result B" in result.content


@pytest.mark.asyncio
async def test_parallel_error_isolation():
    class ErrorLLM:
        async def ainvoke(self, messages):
            raise Exception("fail")

    runtime_a = AgentRuntime(name="a", llm=ErrorLLM(), system_prompt="", tools=[], strategy="parallel")
    runtime_b = AgentRuntime(name="b", llm=MockLLM("Result B"), system_prompt="", tools=[], strategy="parallel")

    engine = CollaborationEngine()
    result = await engine.execute([runtime_a, runtime_b], "query", "parallel")

    assert len(result.agent_results) == 2
    assert result.agent_results[0]["status"] == "error"
    assert result.agent_results[1]["status"] == "ok"
    assert "Result B" in result.content  # Good result still appears


@pytest.mark.asyncio
async def test_unknown_strategy_raises():
    engine = CollaborationEngine()
    with pytest.raises(ValueError, match="Unknown strategy"):
        await engine.execute([], "test", "invalid")
