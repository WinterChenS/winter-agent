# Week 4 - ReAct 图结构设计与实操

> 本周目标：把当前 V0.2 的"单节点图"升级为"ReAct 结构图"，理解条件边与循环，真正搭出一个能判断是否调用工具的 Agent。

---

## 0) 本周你会学到什么

- **ReAct 是什么**：Thought → Action → Observation → Final Answer 的循环模式
- **条件边（Conditional Edge）**：如何让图根据 State 决定走哪条路
- **循环控制**：如何防止 Agent 无限调用工具
- **节点职责划分**：`agent_node` 和 `tool_node` 各负责什么

---

## 1) 从 V0.2 到 V0.3：图长什么样

### 当前 V0.2（单节点）

```text
START → llm_node → END
```

用户说什么就直接回答，没有工具判断。

### 目标 V0.3（ReAct 结构）

```text
START
  ↓
agent_node（LLM 决策：直接回答 OR 调工具）
  ├── current_tool 不为空 → tool_node（执行工具）→ 回到 agent_node（循环）
  └── current_tool 为空 → END（直接返回最终回答）
```

这就是 **ReAct（Reasoning + Acting）** 的核心：

- `agent_node` = **Reasoning**（LLM 决策：这次要行动吗）
- `tool_node` = **Acting**（执行工具，把结果写回 State）
- 再次进入 `agent_node` = **Observation**（LLM 看到工具结果，生成最终答案）

---

## 2) State 升级（在 Week 2 的基础上）

Week 2 你设计了：

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    current_tool: str | None
    tool_result: str | None
    reasoning_steps: list[str]
```

Week 4 需要再加 2 个字段：

```python
    tool_input: dict | None         # 工具调用的具体入参
    iteration_count: int            # 防止无限循环的计数器
```

**为什么需要 `tool_input`？**

`agent_node` 决定要调 search 工具，但"搜什么"需要传给 `tool_node`。
如果没有 `tool_input`，`tool_node` 不知道用什么参数调工具。

**为什么需要 `iteration_count`？**

防止 Agent 在"决策 → 工具 → 决策 → 工具..."中死循环。
条件边会判断：如果 `iteration_count >= MAX_ITERATIONS`，强制结束。

---

## 3) 节点职责（重点：和 Week 3 对应起来）

### `agent_node`

**职责**：LLM 决策节点

1. 读取 `state["messages"]`（历史对话）
2. 如果有 `tool_result`，把它包含在 system prompt 里
3. 调用 LLM，解析响应：
   - 如果 LLM 返回 `{"action": "tool", "tool": "search", "query": "..."}` → 设置 `current_tool` 和 `tool_input`
   - 否则 → 正常文本回答，`current_tool = None`
4. 追加 `reasoning_steps`

**输入 State 字段**：`messages`, `tool_result`, `reasoning_steps`, `iteration_count`

**输出（写回 State）**：`messages`, `current_tool`, `tool_input`, `reasoning_steps`, `iteration_count`

---

### `tool_node`

**职责**：工具执行节点

1. 从 State 读取 `current_tool` 和 `tool_input`
2. 通过 `get_tool_registry().invoke(tool_name, tool_input)` 调用工具
3. 结果写入 `tool_result`
4. 重置 `current_tool = None`（执行完了）
5. 追加 `reasoning_steps`

**输入 State 字段**：`current_tool`, `tool_input`

**输出（写回 State）**：`tool_result`, `current_tool`（重置为 None）, `reasoning_steps`

---

### 条件边函数 `route_after_agent`

```python
def route_after_agent(state: AgentState) -> str:
    if state.get("current_tool") and state.get("iteration_count", 0) < MAX_ITERATIONS:
        return "tool"      # 还需要调工具
    return END             # 直接结束（回答完了 or 超过最大迭代次数）
```

---

## 4) 完整的节点流转图（含 State 变化）

```text
用户输入: "LangGraph 是什么？搜一下"
  ↓
[START]
  ↓
[agent_node]
  State 读: messages=[HumanMessage]
  LLM 决策: {"action": "tool", "tool": "search", "query": "LangGraph"}
  State 写:
    current_tool = "search"
    tool_input = {"query": "LangGraph"}
    iteration_count = 1
    reasoning_steps = ["Decided to call search"]
  ↓
[条件边: current_tool = "search"] → 走 tool_node
  ↓
[tool_node]
  State 读: current_tool="search", tool_input={"query": "LangGraph"}
  执行: registry.invoke("search", {"query": "LangGraph"})
  State 写:
    tool_result = '{"ok": true, "data": {...}}'
    current_tool = None
    reasoning_steps += ["search executed, result stored"]
  ↓
[agent_node]（第二次）
  State 读: messages, tool_result
  system_prompt 加入: "你已获得工具结果，请给出最终回答"
  LLM 生成最终回答
  State 写:
    messages += [AIMessage("LangGraph 是...")]
    current_tool = None
  ↓
[条件边: current_tool = None] → 走 END
  ↓
[END]
```

---

## 5) 本周注意事项（避坑）

1. **`tool_node` 执行完必须重置 `current_tool = None`**
   不重置的话，下一次进入 `agent_node` 时条件边会误判

2. **`iteration_count` 在 `tool_node` 之后不要递增**
   只在 `agent_node` 决定调工具时递增，这样你的计数是"调了几次工具"

3. **`reasoning_steps` 是手动追加**
   因为 State 里没有加 `Annotated` Reducer，所以节点必须自己 `state["reasoning_steps"] + [new_step]`

4. **条件边的函数只能返回字符串**
   返回值必须和 `add_conditional_edges` 第三参数的 key 对应

---

## 6) Week 4 验收标准

- 能口述新图的完整执行路径（不看代码）
- 能解释条件边函数 `route_after_agent` 是怎么工作的
- 能说出 `iteration_count` 的作用和递增时机
- 能说出 `tool_input` 为什么是独立字段而不是放进 `messages`
- 修改 `MAX_ITERATIONS = 1` 时，工具只会被调用一次

---

## 7) 本周验收题（完成后回答我）

1. `route_after_agent` 什么时候返回 `"tool"`？什么时候返回 `END`？
2. `tool_node` 执行完为什么要把 `current_tool` 重置为 `None`？
3. 如果 `agent_node` 决定不调工具，图走到哪里结束？
4. `iteration_count` 的上限在哪里判断？是在节点内部还是条件边？
5. 本次图结构和 V0.2 相比，多了哪条边？为什么这条边能形成循环？

---

## 8) 你的本周复盘模板

```markdown
# Week 4 复盘

## 1) 我对 ReAct 的理解
- 

## 2) 条件边工作机制
- 

## 3) 我觉得最难理解的点
- 

## 4) 验收题答案
1.
2.
3.
4.
5.

## 5) 下周我想做什么
- 
```

