from langgraph.graph import StateGraph, END

from graph.nodes import agent_node, tool_node, chart_node, MAX_ITERATIONS
from graph.state import State


def _route_after_agent(state: State) -> str:
    """
    条件边函数：在 agent_node 执行完后，决定下一步走哪里。

    规则：
    - 如果 agent_node 设置了 current_tool 且 iteration_count <= MAX_ITERATIONS → 走 tool_node
    - 否则（直接回答 / 超出迭代次数）→ END

    ⚠️ 注意：这里必须用 <=，不能用 <。
    agent_node 在 current_iteration == MAX_ITERATIONS 时会强制 fallback（将 current_tool 置 None）。
    所以 routing 这里用 <= 是为了让第 MAX_ITERATIONS 轮工具能真正执行；
    如果用 < 会导致：agent 设置了 current_tool 但 routing 直接走 END，最终答案静默丢失。
    """
    if state.get("current_tool") and state.get("iteration_count", 0) <= MAX_ITERATIONS:
        return "tool"
    return "chart"


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
            END: END,            # 返回 END     → 结束
        },
    )

    # 4. 固定边：tool_node 执行完后，无条件回到 agent_node（形成循环）
    #    agent_node 第二次调用时，会读取 tool_result 生成最终答案
    workflow.add_edge("tool", "agent")

    # 5. 固定边：chart_node 执行完后，输出 ChartSpec 并结束
    workflow.add_edge("chart", END)

    return workflow.compile(checkpointer=checkpointer)
