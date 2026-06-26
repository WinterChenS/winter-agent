import pytest
from unittest.mock import MagicMock
from models.agent import AgentDefinition
from repositories.agent_repository import MockAgentRepository
from core.router_agent import RouterAgent
from core.agent_factory import AgentFactory, AgentRuntime
from core.collaboration import CollaborationEngine


class MockLLM:
    def __init__(self, response: str = "Default response"):
        self.response = response

    async def ainvoke(self, messages):
        return type("R", (), {"content": self.response})()


@pytest.mark.asyncio
async def test_full_multi_agent_pipeline(monkeypatch):
    """E2E: Create agents -> Route -> Build -> Execute -> Verify"""

    # Mock ChatOpenAI in agent_factory so no real API calls are made
    monkeypatch.setattr(
        "core.agent_factory.ChatOpenAI",
        lambda **kw: MockLLM(response=f"Result from {kw.get('model', 'unknown')}"),
    )

    # Mock ToolRegistry for factory
    class MockRegistry:
        def get(self, name):
            mock_tool = MagicMock()
            mock_tool.name = name
            return mock_tool

    monkeypatch.setattr("core.agent_factory.get_tool_registry", lambda: MockRegistry())

    # 1. Setup repository with 2 agents
    repo = MockAgentRepository()
    researcher = AgentDefinition(
        name="researcher",
        display_name="Researcher",
        description="Searches for information",
        system_prompt="You are a researcher. Search and find facts.",
        tools=["search"],
        trigger_keywords=["搜索", "查找", "研究"],
        collaboration_strategy="sequential",
        priority=2,
    )
    analyst = AgentDefinition(
        name="analyst",
        display_name="Analyst",
        description="Analyzes data",
        system_prompt="You are an analyst. Analyze and compute.",
        tools=["search", "execute_python"],
        trigger_keywords=["分析", "计算", "数据"],
        collaboration_strategy="sequential",
        priority=1,
    )
    await repo.create(researcher)
    await repo.create(analyst)

    # 2. RouterAgent matches keyword
    router = RouterAgent(repo)
    result = await router.route("帮我搜索并分析最新数据")
    assert result.source == "keyword"
    assert len(result.agents) >= 1
    assert result.agents[0].name in ["researcher", "analyst"]

    # 3. AgentFactory builds runtimes
    factory = AgentFactory()
    runtimes = [factory.build(a, context={"user_query": "搜索并分析最新数据"}) for a in result.agents]
    assert len(runtimes) >= 1
    for r in runtimes:
        assert isinstance(r, AgentRuntime)
        assert r.system_prompt != ""

    # 4. CollaborationEngine executes
    engine = CollaborationEngine()
    collab_result = await engine.execute(runtimes, "搜索并分析最新数据", result.strategy)
    assert collab_result.content != ""
    assert len(collab_result.agent_results) >= 1

    # 5. Verify agent results have expected fields
    for ar in collab_result.agent_results:
        assert "agent" in ar
        assert "status" in ar
        assert ar["status"] in ["ok", "error"]


@pytest.mark.asyncio
async def test_empty_repo_graceful():
    """Empty repository should not crash -- Router returns empty."""
    repo = MockAgentRepository()
    router = RouterAgent(repo)
    result = await router.route("test query")
    assert result.agents == []
    assert result.source == "none"
