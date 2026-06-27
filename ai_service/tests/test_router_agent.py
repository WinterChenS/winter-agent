from __future__ import annotations

import pytest
from core.router_agent import RouterAgent, RouterResult
from repositories.agent_repository import MockAgentRepository
from models.agent import AgentDefinition


@pytest.fixture
def repo():
    r = MockAgentRepository()
    # Add test agents
    r._agents = {}
    return r


@pytest.fixture
async def populated_repo(repo):
    agents = [
        AgentDefinition(name="researcher", display_name="Researcher", system_prompt="Research",
                       trigger_keywords=["搜索", "查找", "研究"], description="Search and research", priority=2),
        AgentDefinition(name="coder", display_name="Coder", system_prompt="Code",
                       trigger_keywords=["代码", "编程", "bug"], description="Write code", priority=1),
        AgentDefinition(name="writer", display_name="Writer", system_prompt="Write",
                       trigger_keywords=[], description="Write content", priority=0),
    ]
    for a in agents:
        await repo.create(a)
    return repo


@pytest.mark.asyncio
async def test_keyword_match(populated_repo):
    router = RouterAgent(populated_repo)
    result = await router.route("帮我搜索最新的AI新闻")
    assert result.source == "keyword"
    assert len(result.agents) >= 1
    assert result.agents[0].name == "researcher"


@pytest.mark.asyncio
async def test_no_agents_returns_empty(populated_repo):
    empty_repo = MockAgentRepository()
    router = RouterAgent(empty_repo)
    result = await router.route("test")
    assert result.agents == []


@pytest.mark.asyncio
async def test_keyword_matches_best_agent(populated_repo):
    router = RouterAgent(populated_repo)
    result = await router.route("帮我修复这个代码bug")
    assert result.source == "keyword"
    assert result.agents[0].name == "coder"  # keyword "bug" matches coder


@pytest.mark.asyncio
async def test_no_keyword_falls_back_to_llm(populated_repo, monkeypatch):
    # Mock LLM to return specific result
    class MockLLM:
        content: str = '{"agents": ["writer"], "strategy": "sequential"}'

        async def ainvoke(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return self

    monkeypatch.setattr(
        "core.router_agent.ChatOpenAI",
        lambda **kw: type("LLM", (), {"ainvoke": MockLLM().ainvoke})(),
    )

    router = RouterAgent(populated_repo)
    result = await router.route("帮我写一篇文章")
    assert result.source == "llm"
    assert result.agents[0].name == "writer"
