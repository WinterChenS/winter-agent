from langgraph.graph import StateGraph, END
from graph.state import State
from graph.nodes import llm_node


# 创建整体的工作流图：将不同的任务节点串联起来
def create_agent_graph(checkpointer=None):
    # 初始化一个基于我们在 state.py 里定义的 State 的状态机拓扑图
    workflow = StateGraph(State)
    
    # 1. 向图中添加节点（Node）
    # 这里添加了一个名为 "llm" 的节点，它的执行内容指向我们在 nodes.py 里写好的 llm_node 处理器函数
    workflow.add_node("llm", llm_node)
    
    # 2. 设置起点（Entry Point）
    # 规定用户的消息进图的时候，第一步该交给哪个节点进行处理，这里自然是 "llm" 节点
    workflow.set_entry_point("llm")

    # 3. 添加连线（Edge）
    # 表示处理的流转方向：从一个节点流向另一个节点。
    # 这里我们只做了一个非常基础的问答应用，所以告诉程序："llm" 节点思考回答完毕后，就直接结束运行 (到达 END)
    workflow.add_edge("llm", END)
    
    # 把刚才这一套连接图配置编译成实际可以执行的工作流组件并返回
    # 在这里我们挂载刚才传进来的全局检查点管理器（比如 PostgreSQL 保存器）
    return workflow.compile(checkpointer=checkpointer)
