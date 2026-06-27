from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from core.agent_factory import AgentFactory
from core.collaboration import CollaborationEngine
from core.router_agent import RouterAgent
from graph.nodes import answer_node, chart_planner_node
from graph.state import State

logger = logging.getLogger(__name__)


async def router_node(state: State, *, router: RouterAgent) -> dict:
    """Route user query to matching agents."""
    user_query = ""
    for msg in reversed(list(state.get("messages", []))):
        if hasattr(msg, "type") and msg.type == "human":
            user_query = msg.content or ""
            break

    logger.info("[ROUTER] analyzing query: %s", user_query[:80])
    result = await router.route(user_query)
    agent_names = [a.name for a in result.agents]
    logger.info("[ROUTER] selected %d agent(s): %s (strategy=%s source=%s)",
                len(agent_names), agent_names, result.strategy, result.source)

    return {
        "router_result": {
            "agent_names": agent_names,
            "strategy": result.strategy,
            "source": result.source,
        },
        "selected_agents": agent_names,  # Store names only (msgpack-safe)
        "selected_strategy": result.strategy,
    }


async def collaboration_node(state: State, *, factory: AgentFactory, engine: CollaborationEngine, event_bus=None) -> dict:
    """Build agent runtimes and execute collaboration.
    Combined into one node to avoid msgpack serialization of AgentRuntime objects."""
    agent_names = state.get("selected_agents", [])
    strategy = state.get("selected_strategy", "sequential")

    user_query = ""
    for msg in reversed(list(state.get("messages", []))):
        if hasattr(msg, "type") and msg.type == "human":
            user_query = msg.content or ""
            break

    if not agent_names:
        return {"collab_result": None, "route": "answer"}

    # Load agent definitions by name and build runtimes
    from core.runtime import get_agent_repository
    repo = get_agent_repository()
    selected: list = []
    for name in agent_names:
        agents = await repo.list_enabled()
        for a in agents:
            if a.name == name or a.id == name:
                selected.append(a)
                break

    runtimes = [factory.build(a, context={"user_query": user_query}) for a in selected]
    logger.info("[COLLAB] executing with %d agent(s) strategy=%s: %s",
                len(runtimes), strategy, [r.name for r in runtimes])

    result = await engine.execute(runtimes, user_query, strategy)

    return {
        "collab_result": result.content,
        "agent_results": result.agent_results,
        "route": "merge",
    }


async def merge_node(state: State) -> dict:
    """Merge collaboration result into messages. Route to chart_planner for chart extraction."""
    collab_result = state.get("collab_result")
    if collab_result:
        return {
            "messages": [HumanMessage(content=collab_result)],
            "route": "chart_planner",
        }
    return {"route": "chart_planner"}


def _route_from_router(state: State) -> str:
    agents = state.get("selected_agents", [])
    if not agents:
        return "answer"  # No agents → answer directly
    return "collaboration"


def _route_from_collaboration(state: State) -> str:
    return state.get("route", "chart_planner")


def _route_from_merge(state: State) -> str:
    route = state.get("route", "answer")
    return route if route in ("chart_planner", "answer") else "answer"


def create_multi_agent_graph(
    router: RouterAgent,
    factory: AgentFactory,
    engine: CollaborationEngine,
    checkpointer=None,
    event_bus=None,
):
    workflow = StateGraph(State)

    # Multi-agent nodes — wrap async functions for LangGraph
    async def _router(s): return await router_node(s, router=router)
    async def _collaboration(s): return await collaboration_node(s, factory=factory, engine=engine, event_bus=event_bus)

    workflow.add_node("router", _router)
    workflow.add_node("collaboration", _collaboration)
    workflow.add_node("merge", merge_node)

    # Existing pipeline nodes (from graph/nodes.py)
    workflow.add_node("chart_planner", chart_planner_node)
    workflow.add_node("answer", answer_node)

    workflow.set_entry_point("router")

    workflow.add_conditional_edges(
        "router",
        _route_from_router,
        {
            "collaboration": "collaboration",
            "answer": "answer",
        },
    )

    workflow.add_conditional_edges(
        "collaboration",
        _route_from_collaboration,
        {
            "merge": "merge",
            "answer": "answer",
        },
    )

    workflow.add_conditional_edges(
        "merge",
        _route_from_merge,
        {
            "chart_planner": "chart_planner",
            "answer": "answer",
        },
    )

    workflow.add_edge("chart_planner", "answer")
    workflow.add_edge("answer", END)
    # Direct path: router → answer (skip chart_planner when no agents matched)
    workflow.add_edge("answer", END)

    return workflow.compile(checkpointer=checkpointer)
