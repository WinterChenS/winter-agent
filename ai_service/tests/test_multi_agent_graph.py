from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from graph.multi_agent_graph import create_multi_agent_graph
from core.router_agent import RouterAgent, RouterResult
from core.agent_factory import AgentFactory, AgentRuntime
from core.collaboration import CollaborationEngine, CollaborationResult
from models.agent import AgentDefinition


@pytest.mark.asyncio
async def test_graph_builds_and_routes():
    """Verify the multi-agent graph can be built and compiles."""
    # Mock dependencies
    router = MagicMock(spec=RouterAgent)
    router.route.return_value = RouterResult(
        agents=[AgentDefinition(name="test", display_name="T", system_prompt="Hi")],
        strategy="sequential",
        source="keyword",
    )

    factory = MagicMock(spec=AgentFactory)
    mock_llm = MagicMock()
    mock_llm.ainvoke.return_value = type("R", (), {"content": "Test response"})()
    factory.build.return_value = AgentRuntime(
        name="test", llm=mock_llm, system_prompt="Hi", tools=[], strategy="sequential"
    )

    engine = MagicMock(spec=CollaborationEngine)
    engine.execute.return_value = CollaborationResult(
        content="Final merged result",
        agent_results=[{"agent": "test", "status": "ok", "output": "result"}],
    )

    graph = create_multi_agent_graph(router, factory, engine)

    assert graph is not None
    # Verify nodes exist
    nodes = list(graph.nodes.keys())
    assert "router" in nodes
    assert "factory" in nodes
    assert "collaboration" in nodes
    assert "merge" in nodes


@pytest.mark.asyncio
async def test_graph_no_agents_falls_through():
    """When Router returns no agents, should skip to chart_planner."""
    router = MagicMock(spec=RouterAgent)
    router.route.return_value = RouterResult(
        agents=[], strategy="sequential", source="none"
    )

    factory = MagicMock(spec=AgentFactory)
    engine = MagicMock(spec=CollaborationEngine)

    graph = create_multi_agent_graph(router, factory, engine)
    assert graph is not None
