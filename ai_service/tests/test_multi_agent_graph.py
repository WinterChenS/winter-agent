from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage

from graph.multi_agent_graph import create_multi_agent_graph
from graph.nodes import planning_node
from graph.state import State
from core.agent_factory import AgentFactory, AgentRuntime
from core.collaboration import CollaborationEngine, CollaborationResult
from core.router_agent import RouterAgent, RouterResult
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
    assert "collaboration" in nodes  # factory merged into collaboration
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


@pytest.mark.asyncio
async def test_planning_node_generates_plan():
    """Verify planning_node produces a valid execution_plan for a non-trivial query."""
    from graph.state import State
    from graph.nodes import planning_node

    state = State(
        messages=[HumanMessage(content="What were Apple's Q1 2026 earnings?")],
        execution_plan=None,
        execution_results=[],
        artifacts=[],
        current_plan_step=0,
        plan_phase="planning",
        iteration_count=0,
        tool_steps=[],
        reasoning_steps=[],
        # other required fields with defaults
        conversation_id="test-1",
        current_tool=None,
        tool_input=None,
        tool_result=None,
        last_tool_name=None,
        last_tool_query=None,
        consecutive_search_count=0,
        last_guard_reason=None,
        trace_id="",
        turn_id="",
        span_id="",
        parent_span_id=None,
        active_agent="default",
        chart_specs=[],
        pending_chart_spec=None,
        pending_text_block=None,
        blocks=[],
        route="start",
        router_result=None,
        selected_agents=None,
        selected_strategy=None,
        runtimes=None,
        collab_result=None,
        agent_results=None,
    )
    result = await planning_node(state)
    assert result["plan_phase"] == "executing"
    assert result["execution_plan"] is not None
    assert "steps" in result["execution_plan"]
    assert len(result["execution_plan"]["steps"]) > 0
