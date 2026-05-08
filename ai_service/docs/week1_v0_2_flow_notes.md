# Week 1 - V0.2 全链路笔记

## 1) 链路图
Client
 -> POST /api/v1/generate/stream
 -> main.py::stream_generate()
     -> event_generator()
          -> if no api_key: MOCK_RESPONSES
          -> else: create_agent_graph(checkpointer=checkpointer)
          -> graph.astream_events
          -> 过滤 on_chat_model_stream
          -> chunk.content -> SSE token 输出
 -> EventSourceResponse 持续返回

Client
 -> GET /api/v1/history/{conversation_id}
 -> checkpointer.aget_tuple(config)
 -> 返回格式化历史messages

## 2) 关键函数职责
- main.py::lifespan FastApi用来的初始化钩子，在FastApi初始化之前和之后会执行一些资源的初始化和清理
- main.py::stream_generate 对话的主入口，根据是否存在apiKey来判断是否需要mock还是真实的通过graph生成响应
- graph/graph.py::create_agent_graph 创建graph实例，传入checkpointer用于会话历史的记录和读取
- graph/nodes.py::llm_node 大模型的主要定义
- graph/state.py::State 定义了状态对象的接口和基本实现

## 3) Mock vs LLM 分支差异
- Mock分支直接获取随机的预设相应，不会调用大模型
- LLM分支会创建一个agent graph，并通过底层的大模型生成真实的响应


## 4) 我的理解盲点

- llm_node方法明明有入参state，为什么workflow.add_node("llm", llm_node)这里没有传入state？ 这种是什么意思不太懂
- checkpointer的初始化和使用流程不太清晰，尤其是它是如何在整个链路中被调用和更新的
- response = await llm.ainvoke(state["messages"]) 这里怎么将历史信息和当前的提问信息整合在一起也不是很清楚

## 5) 3-5 分钟口述稿
- 项目使用了FastApi来管理API请求，感觉这个类似springboot一样，可以管理生命周期，然后提供web组件
- 在stream_generate中，类似与event_generator这种是内部函数，可以让方法内作为函数调用
- 然后调用create_agent_graph来初始化图，传入的checkpointer是postgresQL实现的，可以通过数据库来管理历史会话
- create_agent_graph中，定义了整个图的结构，当前是一个非常简单的llm，这里感觉像是组建了一个串行路径，后续可以增加更多的节点实现更复杂的功能
- 在event_generator中，判断如果没有apiKey就走mock分支，直接返回预设的响应；如果有apiKey就走真实的生成分支，通过graph来生成响应
- thread_id是用来标示不同的会话的id，可以根据这个来对会话进行隔离
- astream_events是会执行定制好的图的流程，并向外输出信息
- on_chat_model_stream是一个过滤器，用来过滤“大模型正在输出流式的具体字块”这个事件，因为用户只需要这个信息
- yield分部的去输出响应，这样就实现了流式输出的效果

---

## 6) Week 1 验收反馈（由 Copilot 批改）

### ✅ 正确的部分
- 链路图整体结构正确
- Mock vs LLM 分支差异描述准确
- `checkpointer` 初始化位置（`lifespan`）、使用接口（`create_agent_graph`、`get_chat_history`）✅
- SSE 按 token yield 的原因（节省内存、实时输出）✅
- `on_chat_model_stream` 的过滤作用 ✅
- 口述稿逻辑完整，类比 SpringBoot 很恰当 ✅

---

### ⚠️ 需要修正的地方

#### 1. `llm_node` 职责描述偏浅

你写的是：`大模型的主要定义`

更准确应该是：

> `llm_node` 是一个**节点处理函数（Node Handler）**。
> 它的职责是：接收当前 `State`（含历史 messages），调用 LLM，把 LLM 的回复作为新消息追加写回 `State`。
> 它本身不"定义大模型"，它是图中的一个执行单元。

#### 2. `State` 描述漏掉了核心机制

你写的是：`定义了状态对象的接口和基本实现`

更准确应该是：

> `State` 是图在节点间流转数据的**共享记事本**。
> 关键在于 `messages` 字段用了 `Annotated[List, add_messages]`，这意味着每次节点返回新消息时，
> 是**追加（append）**到已有列表末尾，而不是覆盖。
> 这是 LangGraph 的"Reducer"机制，每个字段可以自定义合并策略。

#### 3. `conversation_id → thread_id` 机制答对一半

你说"state 会按照这个进行自动查询"，方向对，但漏了关键步骤：

> 完整流程是：
> 1. `conversation_id` 作为 `thread_id` 放入 `config = {"configurable": {"thread_id": thread_id}}`
> 2. 每次 `graph.astream_events(inputs, config=...)` 执行时，LangGraph 在**运行前**自动从 checkpointer 加载该 thread_id 的上一次 State（含历史 messages）
> 3. 把你本次的新消息 append 进去，一起送给 LLM
> 4. 执行完成后，把最新 State **自动写回** checkpointer（不需要你手动调用 save）
> 
> 所以 checkpointer 的读写都是 LangGraph 内部自动完成的，你只需要在编译时传入它。

#### 4. `State.messages` 合并策略的具体机制

你说"会将当前问题和历史 messages 融合，策略不清楚"——现在补充：

> `add_messages` 是 LangGraph 内置的一个 **Reducer 函数**，它的合并规则是：
> - 新消息追加到已有消息列表末尾（不覆盖）
> - 如果传入相同 `id` 的消息，则会更新（幂等）
>
> 代码体现：
> ```python
> messages: Annotated[List, add_messages]
> ```
> 当 `llm_node` 返回 `{"messages": [response]}` 时，
> LangGraph 自动对 `messages` 字段调用 `add_messages(旧列表, [response])`，
> 结果是追加，而不是替换。
>
> 这对多轮对话非常重要：LLM 每次都能看到完整的对话历史，才能理解上下文。

---

### ⚠️ 错误需要纠正：`add_node` 不传 state 的原因

这是你的一个盲点，答案如下：

> `workflow.add_node("llm", llm_node)` 这里传的是**函数引用**，不是函数调用。
>
> LangGraph 内部在执行图时，会**自动**把当前 State 作为参数传给每个节点函数。
> 你只需要告诉图"这个节点叫 llm，执行时调用 llm_node 这个函数"，
> State 的注入是框架负责的，不需要你手动传。
>
> 类比 Spring 的 `@Bean`：你只是注册了函数，框架在合适时机自动调用并注入依赖。

---

### ⚠️ 历史信息如何整合到 `state["messages"]`

这是你的另一个盲点，完整机制如下：

> 你在 `main.py` 里只传了当前这条：
> ```python
> inputs = {"messages": [HumanMessage(content=request.message)]}
> ```
>
> 但 LangGraph 在真正执行图之前，会先做一步：
> 1. 从 checkpointer 读取该 `thread_id` 上一次保存的 State（里面有历史 messages）
> 2. 用 `add_messages` 策略把你传入的新消息 **merge 进去**
> 3. 得到完整的 `[历史消息1, 历史消息2, ..., 本次用户消息]`
> 4. 这整个列表才被传入 `llm_node` 的 `state["messages"]`
> 5. `llm.ainvoke(state["messages"])` 把这整个列表发给大模型，大模型才有上下文
>
> 所以你不需要手动合并，框架 + checkpointer 帮你做了。

---

### 📊 Week 1 总评

| 项目 | 评分 | 备注 |
|---|---|---|
| 链路图 | ✅ 优秀 | 结构完整 |
| 关键函数职责 | ⚠️ 良好 | llm_node / State 描述需补充 |
| Mock vs LLM 分支 | ✅ 优秀 | 准确 |
| 验收题 Q1(checkpointer) | ✅ 正确 | |
| 验收题 Q2(conversation_id) | ⚠️ 半对 | 漏了自动读写机制 |
| 验收题 Q3(SSE yield) | ✅ 正确 | |
| 验收题 Q4(事件过滤) | ✅ 正确 | |
| 验收题 Q5(messages 合并) | ⚠️ 半对 | 漏了 add_messages 策略 |
| 口述稿 | ✅ 优秀 | 初学者中非常完整 |

**总体评价：Week 1 通过 ✅**

Week 1 核心目标（理解 V0.2 全链路）已达成。遗漏的细节集中在：
1. LangGraph 框架自动注入 State 的机制
2. checkpointer 自动读写 State 的时机
3. `add_messages` 的 Reducer 合并策略

这 3 个点在 Week 2 设计 AgentState 时会非常重要，届时你会更深入理解。

---

**下一步：回复 `开始 Week 2` 开始学习状态设计 AgentState。**
