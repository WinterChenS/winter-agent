from typing import TypedDict, List, Annotated
from langgraph.graph.message import add_messages


# 定义图（Graph）在执行过程中流转的状态（State）结构字典
# 作为初学者，可以把这个理解为一个在节点间互相传递的“公共记事本”
class State(TypedDict):
    # messages 用来存储对话历史（包含用户输入、AI回复等消息内容）
    # Annotated[List, add_messages] 表示每次有新消息来时，将新消息追加（add）到现有列表后面，而不是覆盖掉原有列表
    messages: Annotated[List, add_messages]
    current_tool: str | None
    tool_result: str | None
    reasoning_steps: list[str]
