from langgraph.graph import StateGraph, END
from graph.state import State
from graph.nodes import llm_node


def create_agent_graph():
    workflow = StateGraph(State)
    
    workflow.add_node("llm", llm_node)
    
    workflow.set_entry_point("llm")
    workflow.add_edge("llm", END)
    
    return workflow.compile()
