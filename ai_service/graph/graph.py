from langgraph.graph import StateGraph, END

from graph.nodes import agent_node, tool_node, chart_node, MAX_ITERATIONS
from graph.state import State


def _route_after_agent(state: State) -> str:
    """Route after agent: tool calls go to tool_node, text response loops back to agent,
    chart route goes to chart_node at end."""
    if state.get("current_tool") and state.get("iteration_count", 0) <= MAX_ITERATIONS:
        return "tool"
    # Text response (not final answer yet): loop back to agent to continue ReAct
    consecutive_text = int(state.get("consecutive_text_count", 0) or 0)
    if consecutive_text >= 2:
        return "chart"
    return "agent"  # Self-loop: keep ReAct going


def create_agent_graph(checkpointer=None):
    """
    构建并编译 ReAct Agent 图。

    V0.3 图结构：
        START
          ↓
        agent_node（LLM 决策：需要工具？）
          ├── 需要工具 → tool_node → 回到 agent_node（循环）
          ├── 不需要工具 / 已有答案 → chart_node（图表规划）
          └── chart_node → END
    """
    workflow = StateGraph(State)

    # 1. 注册节点
    workflow.add_node("agent", agent_node)   # LLM 决策节点
    workflow.add_node("tool", tool_node)     # 工具执行节点
    workflow.add_node("chart", chart_node)   # 图表规划 + 生成节点

    # 2. 设置入口：第一步交给 agent_node
    workflow.set_entry_point("agent")

    # 3. 条件边：agent_node 执行完后，由 _route_after_agent 决定走哪里
    #    返回 "tool"  → 走 tool 节点
    #    返回 "chart" → 走 chart 节点
    #    返回 END     → 结束图
    workflow.add_conditional_edges(
        "agent",                 # 从哪个节点出发
        _route_after_agent,      # 路由函数
        {
            "tool": "tool",      # 返回 "tool"  → 走 tool_node
            "chart": "chart",    # 返回 "chart" → 走 chart_node
            "agent": "agent",    # 返回 "agent" → self-loop (continue ReAct)
            END: END,            # 返回 END     → 结束
        },
    )

    # 4. 固定边：tool_node 执行完后，无条件回到 agent_node（形成循环）
    #    agent_node 第二次调用时，会读取 tool_result 生成最终答案
    workflow.add_edge("tool", "agent")

    # 5. 固定边：chart_node 执行完后，输出 ChartSpec 并结束
    workflow.add_edge("chart", END)

    return workflow.compile(checkpointer=checkpointer)
