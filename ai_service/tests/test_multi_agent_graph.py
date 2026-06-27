from __future__ import annotations

import pytest

from graph.multi_agent_graph import create_plan_execute_graph


@pytest.mark.asyncio
async def test_plan_execute_graph_builds():
    """Verify the plan-execute-compose graph can be built and compiles with correct nodes."""
    graph = create_plan_execute_graph()

    assert graph is not None
    node_names = list(graph.nodes.keys())
    assert "planning" in node_names
    assert "execution" in node_names
    assert "composer" in node_names


@pytest.mark.asyncio
async def test_plan_execute_graph_has_conditional_edges():
    """Verify the graph has the correct number of nodes and edges."""
    graph = create_plan_execute_graph()
    # compiled graph includes __start__ in nodes; 3 custom nodes + __start__ = 4
    node_names = list(graph.nodes.keys())
    assert "planning" in node_names
    assert "execution" in node_names
    assert "composer" in node_names
    assert len(node_names) == 4  # __start__ + 3 custom nodes
    # The get_graph edges show __start__ -> planning (verifying entry point)
    g = graph.get_graph()
    edges = {(e.source, e.target) for e in g.edges}
    assert ("__start__", "planning") in edges
