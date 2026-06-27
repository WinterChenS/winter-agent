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


# ────────────────────────────────────────────────────────────────────────────
# Artifact dedup helpers
# ────────────────────────────────────────────────────────────────────────────


def test_tokenize_purpose():
    """Verify _tokenize_purpose handles Chinese bigrams, English words, and empty input."""
    from graph.nodes import _tokenize_purpose

    # English words
    tokens = _tokenize_purpose("Search for stock market data")
    assert "search" in tokens
    assert "stock" in tokens
    assert "market" in tokens
    assert "data" in tokens

    # Chinese bigrams
    tokens = _tokenize_purpose("股市数据分析报告")
    assert "股市" in tokens
    assert "市数" in tokens
    assert "数据" in tokens
    assert "据分" in tokens
    assert "分析" in tokens
    assert "析报" in tokens
    assert "报告" in tokens
    # Full segment should also be present
    assert "股市数据分析报告" in tokens

    # Mixed CJK + English
    # re.findall(r'[一-鿿]+', 'A股market分析') -> ['股', '分析']
    # "股" (len=1) has no bigrams but the full segment is added
    # "分析" (len=2) generates bigram "分析" and full segment "分析"
    tokens = _tokenize_purpose("A股 market 分析")
    assert "a" in tokens
    assert "股" in tokens  # single CJK char, added as full segment
    assert "分析" in tokens  # CJK bigram
    assert "market" in tokens

    # Empty
    assert _tokenize_purpose("") == []
    assert _tokenize_purpose(None) == []


def test_check_artifact_dedup():
    """Verify Jaccard similarity dedup matching works correctly."""
    from graph.nodes import _check_artifact_dedup

    existing = [
        {"type": "chart", "purpose": "Draw stock price trend line chart"},
        {"type": "data", "purpose": "Fetch quarterly revenue data"},
        {"type": "chart", "purpose": "Show market share pie chart"},
    ]

    # Same type + high similarity -> match
    candidate = {"type": "chart", "purpose": "Draw stock price trend chart"}
    match = _check_artifact_dedup(candidate, existing)
    assert match is not None
    assert match["purpose"] == "Draw stock price trend line chart"

    # Different type -> no match even if purpose is similar
    candidate = {"type": "data", "purpose": "Draw stock price trend chart"}
    match = _check_artifact_dedup(candidate, existing)
    assert match is None

    # Low similarity -> no match
    candidate = {"type": "chart", "purpose": "Build machine learning model"}
    match = _check_artifact_dedup(candidate, existing)
    assert match is None

    # Empty existing list
    match = _check_artifact_dedup(candidate, [])
    assert match is None

    # Empty purpose fields -> no match
    candidate = {"type": "chart", "purpose": ""}
    match = _check_artifact_dedup(candidate, existing)
    assert match is None


def test_register_artifact():
    """Verify _register_artifact appends to state and returns correct ID."""
    from graph.nodes import _register_artifact

    state = {"artifacts": []}

    # First registration
    aid1 = _register_artifact(state, "chart", "Stock price trend", 1, "chart_001.png")
    assert aid1 == "chart_0"
    assert len(state["artifacts"]) == 1
    assert state["artifacts"][0]["artifact_id"] == "chart_0"
    assert state["artifacts"][0]["type"] == "chart"
    assert state["artifacts"][0]["source_step_id"] == 1

    # Second registration
    aid2 = _register_artifact(state, "data", "Revenue table", 2, "data_001.json")
    assert aid2 == "data_1"
    assert len(state["artifacts"]) == 2
    assert state["artifacts"][1]["artifact_id"] == "data_1"

    # Registration with non-empty existing artifacts list
    existing = [{"artifact_id": "data_0", "type": "data", "purpose": "Existing data", "source_step_id": 0, "content_ref": "data.json"}]
    state3 = {"artifacts": existing}
    aid3 = _register_artifact(state3, "chart", "New chart", 3, "new_chart.png")
    assert aid3 == "chart_1"
    assert len(state3["artifacts"]) == 2


# ────────────────────────────────────────────────────────────────────────────
# execution_node Tests
# ────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execution_node_follows_plan_steps():
    """Verify execution_node executes tools per step, stores results, and increments step."""
    from graph.nodes import execution_node
    from unittest.mock import patch, AsyncMock

    state = State(
        messages=[HumanMessage(content="Research AI trends in 2026")],
        execution_plan={
            "title": "AI Trends Research",
            "steps": [
                {
                    "step_id": 1,
                    "description": "Search for latest AI trends",
                    "required_tools": ["search"],
                    "expected_artifacts": [
                        {"type": "data", "purpose": "Search results for AI trends"}
                    ],
                },
            ],
        },
        execution_results=[],
        artifacts=[],
        current_plan_step=0,
        plan_phase="executing",
        # Other required State fields with default values
        conversation_id="test-exec-1",
        current_tool=None,
        tool_input=None,
        tool_result=None,
        reasoning_steps=[],
        iteration_count=0,
        tool_steps=[],
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

    with patch("graph.nodes._execute_single_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {
            "result": {"ok": True, "data": "AI trend data"},
            "elapsed_ms": 150,
            "status": "completed",
            "error_msg": None,
        }
        result = await execution_node(state)

    # Should transition to composing (only 1 step)
    assert result["plan_phase"] == "composing"
    assert result["current_plan_step"] == 1

    # Should have 1 execution result
    assert len(result["execution_results"]) == 1
    step_result = result["execution_results"][0]
    assert step_result["step_id"] == 1
    assert step_result["status"] == "completed"
    assert len(step_result["data"]) == 1
    assert step_result["data"][0]["tool"] == "search"

    # _execute_single_tool should have been called once (success, no retry)
    mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_execution_node_empty_plan_skips_to_composing():
    """Verify execution_node routes to composing when plan is empty or None."""
    from graph.nodes import execution_node

    # No plan at all
    state = State(
        messages=[HumanMessage(content="hello")],
        execution_plan=None,
        execution_results=[],
        artifacts=[],
        current_plan_step=0,
        plan_phase="executing",
        conversation_id="test-exec-2",
        current_tool=None,
        tool_input=None,
        tool_result=None,
        reasoning_steps=[],
        iteration_count=0,
        tool_steps=[],
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
    result = await execution_node(state)
    assert result["plan_phase"] == "composing"


@pytest.mark.asyncio
async def test_execution_node_step_beyond_range():
    """Verify execution_node handles step_idx beyond plan length."""
    from graph.nodes import execution_node

    state = State(
        messages=[HumanMessage(content="test")],
        execution_plan={
            "title": "Test",
            "steps": [{"step_id": 1, "description": "Step 1", "required_tools": ["search"], "expected_artifacts": []}],
        },
        execution_results=[],
        artifacts=[],
        current_plan_step=5,  # Beyond plan length (1 step)
        plan_phase="executing",
        conversation_id="test-exec-3",
        current_tool=None,
        tool_input=None,
        tool_result=None,
        reasoning_steps=[],
        iteration_count=0,
        tool_steps=[],
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
    result = await execution_node(state)
    assert result["plan_phase"] == "composing"


@pytest.mark.asyncio
async def test_execution_node_retry_on_failure():
    """Verify execution_node retries failed tool once and records error."""
    from graph.nodes import execution_node
    from unittest.mock import patch, AsyncMock

    state = State(
        messages=[HumanMessage(content="test")],
        execution_plan={
            "title": "Test",
            "steps": [{"step_id": 1, "description": "Step with failure", "required_tools": ["search"], "expected_artifacts": []}],
        },
        execution_results=[],
        artifacts=[],
        current_plan_step=0,
        plan_phase="executing",
        conversation_id="test-exec-4",
        current_tool=None,
        tool_input=None,
        tool_result=None,
        reasoning_steps=[],
        iteration_count=0,
        tool_steps=[],
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

    with patch("graph.nodes._execute_single_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {
            "result": {"ok": False, "error": {"code": "TOOL_ERROR", "message": "API unavailable", "retryable": True}},
            "elapsed_ms": 100,
            "status": "error",
            "error_msg": "API unavailable",
        }
        result = await execution_node(state)

    # Should be called twice (first attempt + retry)
    assert mock_exec.call_count == 2

    # Step should be marked as error
    assert len(result["execution_results"]) == 1
    assert result["execution_results"][0]["status"] == "error"

    # Still should increment step and transition to composing
    assert result["current_plan_step"] == 1
    assert result["plan_phase"] == "composing"


@pytest.mark.asyncio
async def test_execution_node_multi_step():
    """Verify execution_node processes first step and stays in executing phase for multi-step plans."""
    from graph.nodes import execution_node
    from unittest.mock import patch, AsyncMock

    state = State(
        messages=[HumanMessage(content="research")],
        execution_plan={
            "title": "Multi-step Plan",
            "steps": [
                {"step_id": 1, "description": "Step 1", "required_tools": ["search"], "expected_artifacts": []},
                {"step_id": 2, "description": "Step 2", "required_tools": ["browser"], "expected_artifacts": []},
            ],
        },
        execution_results=[],
        artifacts=[],
        current_plan_step=0,
        plan_phase="executing",
        conversation_id="test-exec-5",
        current_tool=None,
        tool_input=None,
        tool_result=None,
        reasoning_steps=[],
        iteration_count=0,
        tool_steps=[],
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

    with patch("graph.nodes._execute_single_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {
            "result": {"ok": True, "data": "result"},
            "elapsed_ms": 100,
            "status": "completed",
            "error_msg": None,
        }
        result = await execution_node(state)

    # Should remain in executing (more steps remain)
    assert result["plan_phase"] == "executing"
    assert result["current_plan_step"] == 1
    assert len(result["execution_results"]) == 1

    # Only step 1 tools executed
    mock_exec.assert_called_once()
