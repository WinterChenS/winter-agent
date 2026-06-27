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
        logger.info("[ROUTE] planning -> execution (phase=%s, steps=%d)", phase, len(plan.get("steps", [])))
        return "execution"
    logger.info("[ROUTE] planning -> composer (phase=%s, has_plan=%s)", phase, bool(plan))
    return "composer"


def _route_from_execution(state: State) -> str:
    """Route execution -> itself (more steps) or -> composer (all done)."""
    phase = state.get("plan_phase", "")
    step_idx = state.get("current_plan_step", 0)
    plan = state.get("execution_plan")
    total_steps = len(plan.get("steps", [])) if plan else 0
    if phase == "composing":
        logger.info("[ROUTE] execution -> composer (phase=composing, step=%d/%d)", step_idx, total_steps)
        return "composer"
    if phase == "executing":
        logger.info("[ROUTE] execution -> execution (phase=executing, step=%d/%d)", step_idx, total_steps)
        return "execution"
    logger.info("[ROUTE] execution -> composer (unknown phase='%s')", phase)
    return "composer"


def create_plan_execute_graph(checkpointer=None, event_bus=None):
    """
    V0.5 Plan -> Execute -> Compose three-phase pipeline:

    Phase 1 (planning): JSON Mode LLM with read-only tools -> generates execution plan
    Phase 2 (execution): Sequential tool execution with artifact dedup (self-loop)
    Phase 3 (composer): Normal Mode streaming LLM -> structured report
    """
    workflow = StateGraph(State)

    # Wrap execution_node with event_bus for tool call events
    async def _execution(s): return await execution_node(s, event_bus=event_bus)

    # Add nodes
    workflow.add_node("planning", planning_node)
    workflow.add_node("execution", _execution)
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
