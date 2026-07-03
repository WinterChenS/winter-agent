---
comet_change: agent-runtime-context-builder
role: technical-design
canonical_spec: openspec
status: draft
archived-with: 2026-07-03-agent-runtime-context-builder
status: final
---

# Agent Runtime Context Builder — Technical Design

## Context

当前仓库的 Agent Runtime 已经具备会话持久化、Graph 执行和 AgentFactory 组装三项基础能力，但缺少统一的运行时上下文构建层：

- [ai_service/db/chat_message_repository.py](ai_service/db/chat_message_repository.py) 已支持按 `conversation_id` 查询历史消息
- [ai_service/api/routes/chat.py](ai_service/api/routes/chat.py) 已持有 `conversation_id`、`agent_id` 和当前用户输入
- [ai_service/core/agent_factory.py](ai_service/core/agent_factory.py) 只做轻量模板替换
- [ai_service/graph/nodes.py](ai_service/graph/nodes.py) 直接在节点里拼 system prompt、工具描述和观察结果

这导致运行时上下文存在三个问题：

1. 会话历史没有被结构化回灌给 Agent
2. prompt 组装逻辑分散，后续 Files / Memory / Knowledge 无法统一接入
3. 缺少预算控制、优先级合并和稳定降级路径

本次设计只落地 backend runtime 基础设施：先把 Session Context 做成真实能力，把 Files / Memory / Knowledge 以同一 provider 契约接入为 stub。

## Goals

- 新增统一 `ContextBuilder` 流程，负责收集、合并、裁剪和注入运行时上下文
- 实现可运行的 `SessionContextProvider`，从已持久化会话历史生成上下文片段
- 定义 Files / Memory / Knowledge provider 的统一接口与空实现
- 在 AgentFactory 和 Graph 节点接入结构化上下文，避免重复查数和重复拼接
- 增加可测试的预算与降级机制

## Non-Goals

- 不实现完整文件上传链路
- 不接入向量数据库、RAG 或企业知识库
- 不修改现有 SSE 事件协议和前端消息协议
- 不在本轮引入 LLM 驱动的对话摘要器

## 1. Architecture

```text
Chat Request
    |
    v
ContextRequest(session_id, agent_id, user_query, max_tokens)
    |
    v
ContextBuilder
    |
    +--> SessionContextProvider --------+
    +--> FileContextProvider (stub) ----+
    +--> MemoryContextProvider (stub) --+--> ContextAssembler --> ContextInjector --> AgentContext
    +--> KnowledgeProvider (stub) ------+
                                                                 |
                                                                 +--> AgentFactory
                                                                 +--> Graph nodes
```

设计原则：

- 收集、合并、注入分层，不把所有逻辑塞进路由或 graph node
- 历史查询只发生一次，消费端共享 `AgentContext`
- provider 失败不阻断请求，统一退化为空片段

## 2. Module Boundaries

建议新增 `ai_service/context/`：

```text
ai_service/context/
├── __init__.py
├── models.py              # ContextRequest / ContextFragment / AgentContext
├── builder.py             # ContextBuilder orchestration
├── assembler.py           # priority merge + trimming
├── injector.py            # render prompt blocks + metadata
├── budget.py              # token/size estimation policy
└── providers/
    ├── __init__.py
    ├── base.py            # ContextProvider protocol
    ├── session.py         # real implementation
    ├── files.py           # stub
    ├── memory.py          # stub
    └── knowledge.py       # stub
```

核心职责：

- `models.py`: 定义跨层共享的数据契约
- `builder.py`: 按注册顺序调用 providers，收集 fragment，并把结果交给 assembler/injector
- `assembler.py`: 负责优先级排序、去重和预算裁剪
- `injector.py`: 生成可注入 prompt 的文本块，以及供 graph/factory 使用的结构化 metadata
- `providers/session.py`: 读取历史消息并过滤不该回灌的内部内容

## 3. Runtime Contracts

```python
@dataclass
class ContextRequest:
    session_id: str | None
    user_query: str
    agent_id: str | None
    max_tokens: int

@dataclass
class ContextFragment:
    provider: str
    content: str
    tokens: int
    priority: int
    metadata: dict

@dataclass
class AgentContext:
    session_id: str | None
    agent_id: str | None
    recent_messages: list[dict]
    fragments: list[ContextFragment]
    rendered_prompt: str
    token_usage: dict[str, int]
    metadata: dict
```

约束：

- provider 输出只产生 `ContextFragment`，不直接改写 prompt
- `AgentContext.rendered_prompt` 是 injector 的产物，不允许消费端二次拼接历史文本
- `metadata` 用于 graph 节点消费结构化信息，避免再次解析 prompt 文本

## 4. Session Provider

`SessionContextProvider` 是本次唯一真实 provider。

行为定义：

- 使用 [ai_service/db/chat_message_repository.py](ai_service/db/chat_message_repository.py) 的 `get_messages_by_conversation()` 拉取会话历史
- 默认只取最近 `N` 条适合回灌的消息，`N` 为可配置常量
- 过滤内部 ReAct/system-only 内容，以及纯工具噪音和用户不可见消息
- 把保留下来的消息格式化为 `recent_messages` 和高优先级 session fragment

过滤规则首版保持保守：

- 保留 `user` / `assistant` 的可见文本
- 对带 `toolCalls` 的消息，只保留用户可见结果摘要，不回灌冗长原始 payload
- 复用 [ai_service/api/routes/chat.py](ai_service/api/routes/chat.py) 已有的内部消息过滤语义，避免行为分叉

## 5. Assembler And Budgeting

优先级固定为：

1. Session
2. Files
3. Memory
4. Knowledge

首版 budget 策略：

- 允许先使用近似 token 估算，而不是强依赖特定 tokenizer
- 若总量超预算，先裁剪低优先级 provider
- 同优先级内优先保留更新的内容，裁掉更旧内容
- 即使全部 provider 都为空，也必须返回合法 `AgentContext`

去重策略首版只做最小实现：

- 相同 provider 的重复文本片段不重复加入
- 不做跨 provider 的语义去重，避免过度设计

## 6. Integration Points

### 6.1 Chat Route

[ai_service/api/routes/chat.py](ai_service/api/routes/chat.py) 负责：

- 从请求读取 `conversation_id`、`agent_id`、用户输入
- 构造 `ContextRequest`
- 调用 `ContextBuilder`
- 把 `AgentContext` 注入 graph 初始 state 或请求上下文

这里不负责手工拼接历史 prompt。

### 6.2 AgentFactory

[ai_service/core/agent_factory.py](ai_service/core/agent_factory.py) 负责：

- 组合 agent 自身 system prompt 模板
- 接收 `AgentContext.rendered_prompt` 作为上下文块
- 保留当前简单变量替换能力，例如 `{current_time}`

目标是让 AgentFactory 消费 builder 结果，而不是自己查询历史。

### 6.3 Graph Nodes

[ai_service/graph/nodes.py](ai_service/graph/nodes.py) 负责：

- 使用 `AgentContext.metadata` 和 `rendered_prompt` 作为执行期上下文基础
- 继续追加当轮工具结果、计划阶段状态和观察结果
- 不重复拼接会话历史

## 7. Failure Handling

Context Builder 不应成为单点阻塞。

降级规则：

- provider 抛错：记录日志，返回空片段
- 历史库不可用：返回空 session context，请求继续执行
- budget 估算异常：回退到保守截断策略
- injector 渲染失败：至少返回空 `rendered_prompt`，不阻断主请求

这样可以保证 V0.7 首版先把架构和真实 session 能力跑通，再逐步加强 provider 质量。

## 8. Testing Strategy

单元测试：

- `SessionContextProvider`：最近 N 条、内部消息过滤、空历史
- `ContextAssembler`：优先级合并、超预算裁剪、空 provider 行为
- `ContextInjector`：输出结构稳定、无 fragment 时仍生成合法结果

集成测试：

- 带 `conversation_id` 的请求会把最近可见历史注入运行时上下文
- 无历史或仓储异常时，请求仍能正常完成
- AgentFactory / graph 节点不会重复注入相同历史

## 9. Trade-offs

- 首版只把 Session 做成真实能力，能最快验证 Context Builder 是否值得存在；代价是 Files / Memory / Knowledge 仍需后续 change 补全
- 预算先做近似估算，能避免引入模型耦合；代价是截断不够精确
- 保留双接入点（factory + graph）但共享同一个 `AgentContext`，能兼容当前结构；代价是初期接线稍多，但比继续散落拼接更可控
