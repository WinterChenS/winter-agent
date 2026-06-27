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

    assert "Result from B: analyzed items, average is 42" in result.content
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

    assert "Done" in result.content
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


@pytest.mark.asyncio
async def test_supervisor_delegates_to_workers():
    # Supervisor LLM that decomposes and then synthesizes
    class SupervisorLLM:
        def __init__(self):
            self.call_count = 0
        async def ainvoke(self, messages):
            self.call_count += 1
            if self.call_count == 1:
                # Decompose response
                return type("R", (), {"content": '[{"worker": "worker_a", "task": "analyze trends"}, {"worker": "worker_b", "task": "summarize"}]'})()
            else:
                # Synthesize response
                return type("R", (), {"content": "Final synthesis of all worker results"})()

    sup = AgentRuntime(name="supervisor", llm=SupervisorLLM(), system_prompt="You are supervisor", tools=[], strategy="supervisor")
    w_a = AgentRuntime(name="worker_a", llm=MockLLM("Trend analysis result"), system_prompt="", tools=[], strategy="supervisor")
    w_b = AgentRuntime(name="worker_b", llm=MockLLM("Summary result"), system_prompt="", tools=[], strategy="supervisor")

    engine = CollaborationEngine()
    result = await engine.execute([sup, w_a, w_b], "analyze and summarize", "supervisor")

    assert len(result.agent_results) >= 3  # supervisor + 2 workers
    assert result.content == "Final synthesis of all worker results"


@pytest.mark.asyncio
async def test_supervisor_fallback_on_decompose_failure():
    class BadDecomposeLLM:
        async def ainvoke(self, messages):
            return type("R", (), {"content": "not valid json"})()

    sup = AgentRuntime(name="supervisor", llm=BadDecomposeLLM(), system_prompt="", tools=[], strategy="supervisor")
    w = AgentRuntime(name="worker", llm=MockLLM("Worker result"), system_prompt="", tools=[], strategy="supervisor")

    engine = CollaborationEngine()
    result = await engine.execute([sup, w], "test", "supervisor")

    # Should fall back to parallel
    assert len(result.agent_results) == 2
