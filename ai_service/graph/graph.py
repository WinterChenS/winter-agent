from langgraph.graph import StateGraph, END

from graph.nodes import agent_node, tool_node, chart_planner_node, answer_node, MAX_ITERATIONS
from graph.state import State


def _route_after_agent(state: State) -> str:
    route = state.get("route", "chart_planner")
    if route == "tool" and int(state.get("iteration_count", 0) or 0) <= MAX_ITERATIONS:
        return "tool"
    return "chart_planner"


def _route_after_tool(state: State) -> str:
    route = state.get("route", "agent")
    return route  # "agent" to loop back


def _route_after_chart_planner(state: State) -> str:
    route = state.get("route", "answer")
    return route  # "answer"


def _route_after_answer(state: State) -> str:
    route = state.get("route", "end")
    return route if route == "end" else END


def create_agent_graph(checkpointer=None):
    """
    V0.4 three-phase pipeline:

    Phase 1: JSON Mode ReAct
        agent_node <--> tool_node (search/browser/time)

    Phase 2: JSON Mode Chart Planning
        chart_planner_node (extracts charts from conversation)

    Phase 3: Normal Mode Streaming Answer
        answer_node (streaming text with [CHART:n] markers)
    """
    workflow = StateGraph(State)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tool", tool_node)
    workflow.add_node("chart_planner", chart_planner_node)
    workflow.add_node("answer", answer_node)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges("agent", _route_after_agent, {
        "tool": "tool",
        "chart_planner": "chart_planner",
        END: END,
    })

    workflow.add_conditional_edges("tool", _route_after_tool, {
        "agent": "agent",
        END: END,
    })

    workflow.add_conditional_edges("chart_planner", _route_after_chart_planner, {
        "answer": "answer",
        END: END,
    })

    workflow.add_conditional_edges("answer", _route_after_answer, {
        "end": END,
        END: END,
    })

    return workflow.compile(checkpointer=checkpointer)
