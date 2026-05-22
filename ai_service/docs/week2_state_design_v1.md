# Week 2 - AgentState v1 设计笔记

> 本周目标：从“看懂 LangGraph 会跑”升级到“我能自己设计一个可扩展的 State”。
>
> 当前项目处于 V0.2：单节点 `llm -> END`
>
> 本周目标对应 roadmap 的 V0.3：为 Tool Calling / ReAct / Agent Loop 提前设计好 `AgentState`。

---

## 0) 本周学习目标

- 理解为什么 LangGraph 的 `State` 是 Agent Runtime 的核心合同（contract）
- 能区分：什么字段应该放进 `State`，什么字段不应该放
- 能独立设计一个面向 V0.3 的 `AgentState v1`
- 能说清楚每个字段由谁写、谁读、怎么合并、是否需要持久化

---

## 1) 先建立一个关键认知：`State` 像不像 LangChain 的 context？

**答案：有点像，但 `State` 比 context 更强。**

你可以先这样理解：

- LangChain 里的 context：更像“喂给模型的上下文材料”
- LangGraph 里的 `State`：更像“整个 Agent 运行时的共享数据面板”

也就是说，`context` 往往只是在模型调用时使用；
而 `State` 不只是给模型看，它还要给：

- 路由节点看
- 工具节点看
- 最终回答节点看
- checkpointer 持久化
- 条件分支判断逻辑看

### 一个更准确的类比

你可以把 `State` 理解为：

> **一次会话在 LangGraph Runtime 中流转的“共享工作内存 + 持久化快照”**

所以本周最重要的一句话是：

> `State` 不只是“上下文”，而是“图运行时的事实来源（source of truth）”。

---

## 2) 结合当前项目，先看 V0.2 的 State 基线

当前 `graph/state.py`：

```text
class State(TypedDict):
	messages: Annotated[List, add_messages]
	input: str
	output: str
```

### 当前真实用到的字段

从当前代码看：

- 真正核心在用的是 `messages`
- `input` / `output` 目前几乎没有在主流程里发挥关键作用

也就是说：

> 现在的 `State` 还是“聊天系统 State”，还不是“Agent State”。

这正是 Week 2 要升级的地方。

---

## 3) 为什么 V0.3 一定要先设计 State？

因为你要从：

```text
用户问题 -> LLM -> 结束
```

升级为：

```text
用户问题
  -> Agent 判断是否需要工具
  -> 如果需要：选择工具
  -> 执行工具
  -> 接收工具结果
  -> 再组织最终回答
```

一旦进入这条链路，你就不再只需要 `messages` 了。

你至少要保存：

- 当前准备调用哪个工具
- 工具执行结果是什么
- 中间推理步骤是什么
- 是否还要继续循环

所以：

> **State 设计，决定了后面的图怎么长。**

---

## 4) AgentState v1 设计原则

本周先记住这 4 条原则：

### 原则 1：每个字段都必须回答 4 个问题

1. 谁写入它？
2. 谁读取它？
3. 怎么合并它？
4. 是否需要持久化？

如果这 4 个问题答不出来，这个字段大概率不该加。

### 原则 2：优先设计“运行必需字段”，不要提前堆字段

先为 V0.3 P0 设计：

- Tool Calling
- ReAct Loop
- Search Tool

不要一上来就设计到 V0.6 / V1.0。

### 原则 3：区分“长期对话信息”和“本轮临时运行信息”

例如：

- `messages`：偏长期，会被 checkpointer 持久化
- `current_tool`：偏当前轮次运行状态
- `tool_result`：可能短期有用，但是否长期保存要谨慎考虑

### 原则 4：Reducer 规则必须明确

在 LangGraph 中，字段不是简单覆盖就完事了。

你必须想清楚：

- 这个字段是追加？
- 覆盖？
- 去重后追加？
- 出错时是否清空？

---

## 5) 推荐的 `AgentState v1`

这是基于你当前项目和 roadmap，最适合初学者的版本。

```text
class AgentState(TypedDict):
	messages: Annotated[list, add_messages]
	current_tool: str | None
	tool_result: str | None
	reasoning_steps: list[str]
```

下面不是背定义，而是要理解“为什么是这 4 个”。

### 5.1 `messages`

**作用**

- 保存对话历史
- 保存用户输入、AI 回复
- 未来也可以保存工具调用后的补充消息

**谁写**

- 当前的 `llm_node`
- 未来的 `agent_node`
- 未来可能还有 `tool_node`（把 observation 转成消息）

**谁读**

- `llm_node`
- `agent_node`
- `final_node`

**合并策略**

- `add_messages` 追加

**是否持久化**

- 是，必须持久化

**为什么必须保留**

- 没有它，多轮对话就断了

---

### 5.2 `current_tool`

**作用**

- 记录“当前决定要调用哪个工具”

**谁写**

- 未来的 `router_node` 或 `agent_node`

**谁读**

- `tool_node`

**合并策略**

- 覆盖（最新决策覆盖旧值）

**是否持久化**

- 可以持久化，但它更偏运行态字段

**为什么现在就要加**

- 这是“从 Chat 升级到 Agent”的第一个标志字段

---

### 5.3 `tool_result`

**作用**

- 记录工具执行结果

**谁写**

- `tool_node`

**谁读**

- `agent_node`
- `final_node`

**合并策略**

- 覆盖（通常只关心最近一次工具结果）

**是否持久化**

- 取决于产品需要
- 学习阶段可以先持久化，便于调试

**为什么需要它**

- 没有它，工具调用和最终回答之间就断链了

---

### 5.4 `reasoning_steps`

**作用**

- 记录中间判断过程，例如：
  - “这个问题需要搜索”
  - “我决定调用 search 工具”
  - “我拿到搜索结果后准备总结”

**谁写**

- `router_node`
- `agent_node`

**谁读**

- 调试日志
- 未来前端 reasoning 展示
- 未来审计或回放

**合并策略**

- 追加列表

**是否持久化**

- 学习阶段建议持久化，方便回放

**为什么很重要**

- 这是你从“黑���聊天”走向“可观察 Agent”的关键一步

---

## 6) 每个字段的“写入节点 / 读取节点 / 生命周期”表

| 字段 | 当前 V0.2 谁写 | V0.3 谁写 | 谁读 | 合并策略 | 生命周期 |
|---|---|---|---|---|---|
| `messages` | `llm_node` | `agent_node` / `final_node` / 可能的 `tool_node` | 全部核心节点 | `add_messages` 追加 | 长期 |
| `current_tool` | 暂无 | `router_node` / `agent_node` | `tool_node` | 覆盖 | 短期 |
| `tool_result` | 暂无 | `tool_node` | `agent_node` / `final_node` | 覆盖 | 短期或中期 |
| `reasoning_steps` | 暂无 | `router_node` / `agent_node` | 调试 / UI / `final_node` | 追加 | 中期 |

---

## 7) 从 V0.2 到 V0.3，图会怎么变化？

### 当前 V0.2

```text
START -> llm -> END
```

### 未来 V0.3（概念图）

```text
START
  -> router_node
	  ├── 需要工具 -> tool_node -> agent_node -> final_node -> END
	  └── 不需要工具 -------------------------------> final_node -> END
```

这时你应该马上意识到：

- `router_node` 需要把“是否需要工具”的判断写进 State
- `tool_node` 需要从 State 里读出工具名
- `tool_node` 执行后要把结果写回 State
- `final_node` 需要综合 `messages + tool_result + reasoning_steps`

这就是为什么 Week 2 先做状态设计，而不是直接冲去写工具。

---

## 8) 本周你最容易犯的 5 个错误

### 错误 1：把 `State` 当成“只有 messages 的上下文包”

修正：

> `State` 是整个图运行时的共享数据面板，不只是给 LLM 的 prompt 上下文。

### 错误 2：字段只会加，不会删

修正：

> 任何字段都必须回答“谁写、谁读、怎么合并、是否持久化”。

### 错误 3：不知道字段应该覆盖还是追加

修正：

> `messages` / `reasoning_steps` 更适合追加；`current_tool` / `tool_result` 更适合覆盖。

### 错误 4：把所有字段都长期持久化

修正：

> 有些字段只是当前步骤临时运行态，不一定要长期存。

### 错误 5：只会写字段名，不会画数据流

修正：

> 设计 `State` 时一定要同时画出：哪个节点写、哪个节点读、字段怎么变化。

---

## 9) Week 2 实操任务

### 任务 A：先批判当前 `State`

请你回答：

1. 当前 `State` 里的 `input` 为什么不够有价值？ 答：因为input当前没有被任何节点使用，并且messages里面已经包含了所有的信息
2. 当前 `State` 里的 `output` 为什么不够适合未来 Agent Loop？ 因为Agent Loop 可能多轮调用工具，每轮工具的调用结果都很重要，当前字段是一个单一的字符串，每次都会被覆盖，不适合记录多轮工具调用的结果。
3. 如果要支持 Tool Calling，为什么仅有 `messages` 不够？ 因为需要让别的节点tool_node知道当前需要调用哪个工具，并且工具调用的结果是什么，这些信息如果只存在messages里，既不清晰也不方便其他节点读取。

### 任务 B：写出你的 `AgentState v1`

请你先不要写代码，先写设计稿：

```text
class AgentState(TypedDict):
	messages: Annotated[list, add_messages]
	current_tool: str | None
	tool_result: str | None
	reasoning_steps: list[str]
```

然后逐个解释每个字段。
messages: 记录对话历史，支持多轮对话和工具调用之后的补充信息
current_tool: 记录当前调用的工具，让tool_node知道要调用哪个工具
tool_result: 记录工具调用的结果，供agent_node和final_node使用
reasoning_steps: 记录中间推理的步骤，供调试和未来的UI展示使用

### 任务 C：给每个字段做“4 问表”

| 字段 | 谁写                       | 谁读                    | 怎么合并 | 是否持久化 |
|---|--------------------------|-----------------------|------|-------|
| messages | llm,tool_node,agent_node | agent_node,final_node | 追加   | 是     |
| current_tool | router_node,agent_node   | tool_node/路由条件        | 覆盖 | 否 |
| tool_result | tool_node                | agent_node,final_node | 覆盖 | 视情况 |
| reasoning_steps | router_node,agent_node   | 调试日志,UI,final_node    | 追加 | 视情况 |

### 任务 D：画出字段流转图

至少画出：

```text
router_node -> tool_node -> final_node
```

并标注：

- 哪个节点写 `current_tool` 答：router_node或agent_node
- 哪个节点写 `tool_result` 答：tool_node
- 哪个节点追加 `reasoning_steps` 答：router_node或agent_node

---

## 10) 本周验收标准

如果你完成得不错，你应该能回答这 6 题：

1. 为什么 `State` 不能只看成 LangChain 的 context？ 答：因为State不仅仅是给模型看的上下文，它还是整个agent运行时的共享数据面板，路由节点、工具节点、最终节点都需要读取它，checkpointer也需要持久化它，所以它是整个Agent Runtime的事实来源，而不仅仅是模型调用的上下文材料。
2. `messages` 和 `reasoning_steps` 为什么更适合追加？答：因为需要让整个对话历史和推理步骤都要被完整的记录下来，覆盖的话就会丢失之前的信息，从而断掉对话和推理的连续性，使得大模型没有之前的记忆；
3. `current_tool` 为什么更适合覆盖？ 答：因为agent_node或者是router_node每次决策调用哪个工具之后，都交由后续的tool_node节点来进行调用，并且输出结果，每次调用完成之后将结果输出到tool_result之后，下一轮会决策出新的工具名称
4. `tool_result` 为什么不能只存在工具函数局部变量里？答：因为需要将结果传递到agent_node或者final_node中进行其他的处理
5. 当前 `State` 里的 `input/output` 为什么不适合直接沿用到 V0.3？ 答：因为这两个字段没有任何意义，messages里面已经记录的历史会话
6. 如果以后要支持多工具循环，你会再给 `State` 增加什么字段？为什么？ 答：添加tools字段，可以使用列表，在tool_node执行了current_tool之后，从列表中pop出下一个需要调用的tool，设置到current_tool，方便下一个工具进行调用
**正解**：不需要加 tools 字段。
多工具循环应该通过：
iteration_count / max_iterations 字段控制循环深度
每次工具结果用 add_messages 追加回 messages
router_node / agent_node 基于最新的 messages 重新决策
这样就能自然地支持多轮工具循环，而不需要在 State 里维护 tools 列表。
---

## 11) 你的本周笔记模板（请直接填写）

```markdown
# Week 2 - AgentState v1 设计笔记

## 1) 我对 State 的新理解
- 是所有节点和组件的数据共享面板

## 2) 当前 V0.2 State 的问题
- 不支持工具调用
- 没有推理过程

## 3) 我设计的 AgentState v1
```text
class AgentState(TypedDict):
	messages: Annotated[list, add_messages]
	current_tool: str | None
	tool_result: str | None
	reasoning_steps: list[str]
```

## 4) 字段设计说明
- `messages`: 记录对话历史，支持多轮对话和工具调用之后的补充信息
- `current_tool`: 记录当前调用的工具，让tool_node知道要调用哪个工具
- `tool_result`: 记录工具调用的结果，供agent_node和final_node使用
- `reasoning_steps`: 记录中间推理的步骤，供调试和未来的UI展示使用

## 5) 字段 4 问表
| 字段 | 谁写  | 谁读                    | 怎么合并 | 是否持久化 |
|---|-----|-----------------------|------|-------|
| messages | llm | agent_node,final_node | 追加   | 是     |
| current_tool | router_node,agent_node | tool_node             | 覆盖 | 否 |
| tool_result | tool_node | agent_node,final_node | 覆盖 | 视情况 |
| reasoning_steps | router_node,agent_node | 调试日志,UI,final_node    | 追加 | 视情况 |

## 6) V0.3 概念图
```text
START
  -> router_node
	  ├── 需要工具 -> tool_node -> agent_node -> final_node -> END
	  └── 不需要工具 -------------------------------> final_node -> END
```

## 7) 我目前的疑问
 
```
不清楚具体这些节点怎么组织起来，因为目前还没有清晰的架构能力
---

## 12) 我给你的学习建议（本周最重要）

本周**先不要急着改代码**。

你现在最需要形成的是：

> “看到一个 Agent 图，我能反推出它需要什么 State；看到一个 State，我能判断它支持什么样的图。”

这才是从“会调 API”走向“会设计 Agent Runtime”的关键一步。

---

## 13) 本周最小行动清单

- [x] 阅读当前 `graph/state.py`
- [x] 回答任务 A 的 3 个问题
- [x] 设计自己的 `AgentState v1`
- [x] 完成字段 4 问表
- [x] 画出 V0.3 概念图
- [x] 把结果发给我做 Week 2 第一次验收

---

## 14) 你完成后给我发什么？

你完成后，直接把这 3 样发给我：

1. 你写好的 `AgentState v1`
2. 你的字段 4 问表
3. 你的 2-3 个疑问

我会按 Week 2 标准帮你修改改，并指出：

- 哪些字段是必须的
- 哪些字段是过度设计
- 哪些字段的合并策略不合理
- 下一周写 Tool Registry 前你还缺哪块认知

