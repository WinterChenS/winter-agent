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
        "selected_agents": result.agents,
        "selected_strategy": result.strategy,
    }


async def factory_node(state: State, *, factory: AgentFactory) -> dict:
    """Build AgentRuntime instances from selected agent definitions."""
    agents = state.get("selected_agents", [])
    if not agents:
        return {"runtimes": [], "route": "chart_planner"}

    user_query = ""
    for msg in reversed(list(state.get("messages", []))):
        if hasattr(msg, "type") and msg.type == "human":
            user_query = msg.content or ""
            break

    runtimes = [factory.build(a, context={"user_query": user_query}) for a in agents]

    return {"runtimes": runtimes}


async def collaboration_node(state: State, *, engine: CollaborationEngine) -> dict:
    """Execute multi-agent collaboration."""
    runtimes = state.get("runtimes", [])
    strategy = state.get("selected_strategy", "sequential")
    logger.info("[COLLAB] executing with %d agent(s) strategy=%s", len(runtimes), strategy)

    user_query = ""
    for msg in reversed(list(state.get("messages", []))):
        if hasattr(msg, "type") and msg.type == "human":
            user_query = msg.content or ""
            break

    if not runtimes:
        return {"collab_result": None, "route": "chart_planner"}

    result = await engine.execute(runtimes, user_query, strategy)

    return {
        "collab_result": result.content,
        "agent_results": result.agent_results,
        "route": "merge",
    }


async def merge_node(state: State) -> dict:
    """Merge collaboration result into messages for the downstream pipeline.
    Skip chart_planner when we have a result — go directly to answer for streaming."""
    collab_result = state.get("collab_result")
    if collab_result:
        return {
            "messages": [HumanMessage(content=collab_result)],
            "route": "answer",
        }
    return {"route": "answer"}


def _route_from_router(state: State) -> str:
    agents = state.get("selected_agents", [])
    if not agents:
        return "answer"  # No agents → answer directly
    return "factory"


def _route_from_factory(state: State) -> str:
    runtimes = state.get("runtimes", [])
    return "collaboration" if runtimes else "chart_planner"


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
):
    workflow = StateGraph(State)

    # Multi-agent nodes
    workflow.add_node("router", lambda s: router_node(s, router=router))
    workflow.add_node("factory", lambda s: factory_node(s, factory=factory))
    workflow.add_node("collaboration", lambda s: collaboration_node(s, engine=engine))
    workflow.add_node("merge", merge_node)

    # Existing pipeline nodes (from graph/nodes.py)
    workflow.add_node("chart_planner", chart_planner_node)
    workflow.add_node("answer", answer_node)

    workflow.set_entry_point("router")

    workflow.add_conditional_edges(
        "router",
        _route_from_router,
        {
            "factory": "factory",
            "answer": "answer",
            "chart_planner": "chart_planner",
        },
    )

    workflow.add_conditional_edges(
        "factory",
        _route_from_factory,
        {
            "collaboration": "collaboration",
            "chart_planner": "chart_planner",
        },
    )

    workflow.add_conditional_edges(
        "collaboration",
        _route_from_collaboration,
        {
            "merge": "merge",
            "chart_planner": "chart_planner",
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
