from typing import Any, TypedDict, List, Annotated
from langgraph.graph.message import add_messages


# 定义图（Graph）在执行过程中流转的状态（State）结构字典
# 作为初学者，可以把这个理解为一个在节点间互相传递的"公共记事本"
class State(TypedDict):
    # messages 用来存储对话历史（包含用户输入、AI回复等消息内容）
    # Annotated[List, add_messages] 表示每次有新消息来时，将新消息追加（add）到现有列表后面，而不是覆盖掉原有列表
    messages: Annotated[List, add_messages]

    # 当前会话 ID（用于策略与审计上下文透传）
    conversation_id: str

    # ── Week 3 ──────────────────────────────────────────────────────────
    # 当前决定要调用的工具名（如 "search"），None 表示不需要调工具
    current_tool: str | None

    # 工具调用的具体入参（如 {"query": "LangGraph"}）
    # 与 current_tool 配套：agent_node 写入，tool_node 读取后执行
    tool_input: dict | None

    # 最近一次工具执行的结果（JSON 字符串），供 agent_node 第二次调用时参考
    tool_result: str | None

    # 中间推理步骤列表，记录每个节点的决策过程，供调试/UI 展示使用
    # 注意：没有加 Reducer，节点需要手动追加：state["reasoning_steps"] + [new_step]
    reasoning_steps: list[Any]

    # ── Week 4 ──────────────────────────────────────────────────────────
    # 工具调用次数计数器，用于防止 Agent 无限循环调用工具
    # 条件边会检查：iteration_count >= MAX_ITERATIONS 时强制跳到 END
    iteration_count: int

    # ── Week 5 ──────────────────────────────────────────────────────────
    # 工具执行步骤列表：记录每次工具调用的详细信息（名称、输入、状态等）
    # 用于在 SSE 最后统一发送 tool_summary 事件，前端单独渲染为"工具步骤"消息区域
    # 格式：[{"tool": "search", "input": "...", "status": "completed"}]
    tool_steps: list[dict]

    # 最近一次工具调用标记（用于去重，避免同一轮重复调用同一工具同一query）
    last_tool_name: str | None
    last_tool_query: str | None
    consecutive_search_count: int
    last_guard_reason: dict | None

    # ── V0.3 observability ───────────────────────────────────────────────
    trace_id: str
    turn_id: str
    span_id: str
    parent_span_id: str | None
    active_agent: str

    # ── Chart rendering ──────────────────────────────────────────────────
    chart_specs: list[dict]     # List of ChartSpec dicts (multi-chart support)
    pending_chart_spec: dict | None  # Chart spec ready for immediate SSE emission
    pending_text_block: str | None   # Text block ready for immediate SSE emission
    blocks: list[dict]          # Ordered content blocks (markdown/chart/table/code)

    # ── V0.4 three-phase routing ─────────────────────────────────────────
    route: str  # "tool" | "chart_planner" | "answer" | "end"

