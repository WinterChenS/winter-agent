from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from graph.nodes import (
    planning_node,
    execution_node,
    composer_node,
)
from graph.state import State

logger = logging.getLogger(__name__)


def _route_from_planning(state: State) -> str:
    """Route planning -> execution (has plan steps) or -> composer (empty/skip)."""
    phase = state.get("plan_phase", "")
    plan = state.get("execution_plan")
    if phase == "executing" and plan and plan.get("steps"):
        return "execution"
    return "composer"


def _route_from_execution(state: State) -> str:
    """Route execution -> itself (more steps) or -> composer (all done)."""
    phase = state.get("plan_phase", "")
    if phase == "composing":
        return "composer"
    return "execution"


def create_plan_execute_graph(checkpointer=None):
    """
    V0.5 Plan -> Execute -> Compose three-phase pipeline:

    Phase 1 (planning): JSON Mode LLM with read-only tools -> generates execution plan
    Phase 2 (execution): Sequential tool execution with artifact dedup (self-loop)
    Phase 3 (composer): Normal Mode streaming LLM -> structured report
    """
    workflow = StateGraph(State)

    # Add nodes
    workflow.add_node("planning", planning_node)
    workflow.add_node("execution", execution_node)
    workflow.add_node("composer", composer_node)

    # Entry point
    workflow.set_entry_point("planning")

    # Conditional edges
    workflow.add_conditional_edges(
        "planning",
        _route_from_planning,
        {
            "execution": "execution",
            "composer": "composer",
        },
    )

    workflow.add_conditional_edges(
        "execution",
        _route_from_execution,
        {
            "execution": "execution",
            "composer": "composer",
        },
    )

    # Composer always routes to END
    workflow.add_edge("composer", END)

    return workflow.compile(checkpointer=checkpointer)
