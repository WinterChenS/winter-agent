## Context

当前仓库已经具备两块可直接复用的基础能力：

- `ai_service/db/chat_message_repository.py` 已支持按 `conversation_id` 查询完整历史
- `ai_service/api/routes/chat.py` 已在 Graph 输入中传递 `conversation_id` 和 `active_agent`

但运行时上下文仍然停留在两种分散做法：

- `AgentFactory.build()` 只做简单模板替换，例如 `{current_time}`
- `graph/nodes.py` 在节点内部直接拼系统提示词、工具描述和上轮工具结果

这意味着会话上下文、文件上下文、记忆上下文、知识上下文都没有统一入口，也没有预算控制和去重逻辑。

## Goals / Non-Goals

**Goals**

- 让 Agent Runtime 具备统一的上下文构建入口，并优先实现真实可用的 Session Context
- 定义 provider 协议和 assembler，使 Files / Memory / Knowledge 能按同一模式接入
- 将最终上下文以结构化对象注入 AgentFactory 和图执行节点
- 为摘要、预算、去重留出明确扩展点

**Non-Goals**

- 不在本 change 内实现完整文件上传系统
- 不在本 change 内实现向量数据库或企业知识库接入
- 不改变现有 SSE 协议或前端消息协议

## Decisions

### 1. 先做真实 Session，其他 provider 先落骨架

V0.7 的目标是建立 Context Builder，不要求一次性做完全部数据源。当前仓库已有会话历史持久化，因此第一阶段优先实现：

- `SessionContextProvider`：读取最近 N 条用户/助手消息
- `ContextAssembler`：按优先级合并片段并执行 token 截断
- `ContextInjector`：输出给 AgentFactory / Graph 使用的标准文本与元数据

Files / Memory / Knowledge 在本 change 内至少提供：

- 统一 provider 接口
- 空实现或 stub 返回
- 清晰的接入点和测试占位

### 2. 运行时契约独立于具体 Agent

新增运行时模型：

```python
ContextRequest(session_id, user_query, agent_id, max_tokens)
ContextFragment(provider, content, tokens, priority, metadata)
AgentContext(session_id, agent_id, recent_messages, fragments, rendered_prompt, token_usage)
```

这样可以把“收集上下文”和“消费上下文”解耦，避免上下文逻辑继续散落在路由、graph node 和 agent factory 之间。

### 3. 先做服务器端模板化摘要，不在首版引入 LLM 摘要依赖

首版的摘要策略应尽量确定性：

- 默认保留最近 N 轮原始消息
- 超预算时优先截断更旧消息
- 预留 `ConversationSummarizer` 接口，但不把 LLM 摘要作为首版阻塞项

这样可以先把 Context Builder 跑通，再在后续 change 中引入真正的对话摘要器。

### 4. Prompt 接入分两层

- `AgentFactory` 负责静态 agent prompt 模板 + Context Builder 输出的结构化上下文
- `graph/nodes.py` 负责执行期补充，如工具结果、阶段状态、当轮观测信息

两层都必须通过统一的 Context Builder 契约消费上下文，避免重复查询历史。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| 首版只实现 Session，和 V0.7 文档的四类上下文有差距 | 通过 provider 骨架和 spec 明确 Files / Memory / Knowledge 的接入契约，而不是伪实现 |
| token 预算估算不精确 | 首版允许基于字符数/近似 token 估算，封装为可替换策略 |
| Graph 节点与 AgentFactory 都接上下文，容易重复注入 | 统一由 Context Builder 返回分层字段，消费端只读取所需字段 |
| 历史消息直接注入可能带入工具噪音 | provider 内过滤内部消息和非用户可见内容 |

## Open Questions

- Files Context 的首个真实来源是“上传文件”还是“图表/产物 artifact”
- Memory Context 是优先走本地规则存储，还是直接对接后续 Knowledge/Memory 能力
- 首版是否需要把 context 使用统计透出到 observability 事件中