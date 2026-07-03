# Comet Design Handoff

- Change: agent-runtime-context-builder
- Phase: design
- Mode: compact
- Context hash: 85e40d6b6ef4185f89ea2e7562e5d3462ae556b9c24e963e9261cb90352905bf

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/agent-runtime-context-builder/proposal.md

- Source: openspec/changes/agent-runtime-context-builder/proposal.md
- Lines: 1-38
- SHA256: 3638aeeeb28c99b664e37df95d4997a51ae77920b3df6d60742f917ef2824e76

```md
## Why

当前 Agent 运行时每次请求只拼接即时用户输入、工具描述和少量模板变量，缺少统一的上下文构建层。现状有三个直接问题：

- 会话历史虽然已经持久化到 `chat_messages`，但在运行时没有被结构化回灌给 Agent
- Agent prompt 组装分散在 `ai_service/core/agent_factory.py` 和 `ai_service/graph/nodes.py`，没有统一 token 预算和优先级策略
- V0.7 路线图定义了 Session / Files / Memory / Knowledge 四类上下文，但代码里还没有对应抽象，后续能力无法渐进接入

如果继续在各个节点手工拼 prompt，后续记忆、文件和知识检索都会变成横向复制粘贴，难以验证、难以限流，也难以演进为稳定的 Agent Runtime。

## What Changes

- 新增 `ContextBuilder` 主流程，统一收集、裁剪并组装运行时上下文
- 新增上下文契约：`ContextRequest`、`ContextFragment`、`AgentContext`
- 新增 `SessionContextProvider`，从会话历史仓储提取最近消息并生成可注入片段
- 新增 provider 注册/编排层，为 Files / Memory / Knowledge 预留可插拔接口
- 在 `AgentFactory` 和 Graph prompt 构建处接入 Context Builder，替代散落的字符串拼接
- 增加 token budget 与优先级合并规则，默认顺序为 Session > Files > Memory > Knowledge
- 为后续文件、记忆、知识能力先落地最小可运行骨架与测试，不在本 change 内引入完整 RAG 或上传系统

## Capabilities

### New Capabilities

- `agent-runtime-context-builder`: 为 Agent Runtime 构建会话/文件/记忆/知识四类上下文的统一编排层

### Modified Capabilities

- `agent-execution-plan`: 运行时 prompt 组装改为依赖结构化上下文，而不是节点内零散拼接

## Impact

- `ai_service/core/agent_factory.py`
- `ai_service/core/runtime.py`
- `ai_service/api/routes/chat.py`
- `ai_service/graph/nodes.py`
- `ai_service/db/chat_message_repository.py`
- 新增 `ai_service/context/` 或等价 runtime context 模块
- 新增对应单元测试与集成测试```

## openspec/changes/agent-runtime-context-builder/design.md

- Source: openspec/changes/agent-runtime-context-builder/design.md
- Lines: 1-87
- SHA256: 5a1d48ce3a9422e20439322512b493bf273adc861b8578d1e13c8d84338e867f

[TRUNCATED]

```md
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
```

Full source: openspec/changes/agent-runtime-context-builder/design.md

## openspec/changes/agent-runtime-context-builder/tasks.md

- Source: openspec/changes/agent-runtime-context-builder/tasks.md
- Lines: 1-27
- SHA256: 2e0b27a22b79445bc07b5884994067ae3a8e030aff0cc4bd98935b96c181e524

```md
## 1. Runtime Context Contracts

- [ ] 1.1 新增运行时上下文模型：`ContextRequest`、`ContextFragment`、`AgentContext`
- [ ] 1.2 新增 provider 抽象与注册机制，支持按优先级收集上下文片段
- [ ] 1.3 新增 token budget/截断策略的最小实现与测试

## 2. Session Context MVP

- [ ] 2.1 基于 `chat_message_repository` 实现 `SessionContextProvider`
- [ ] 2.2 过滤内部消息与非用户可见工具噪音，只保留适合回灌的历史内容
- [ ] 2.3 支持最近 N 轮历史加载与超预算裁剪

## 3. Builder Integration

- [ ] 3.1 在 `AgentFactory` 接入 Context Builder，替代当前单纯模板变量替换的上下文拼接
- [ ] 3.2 在 `graph/nodes.py` 接入结构化上下文，统一处理系统 prompt 与执行期上下文
- [ ] 3.3 保持当前请求链路兼容：无历史、无可用 provider 时仍可正常响应

## 4. Future Provider Skeletons

- [ ] 4.1 新增 Files / Memory / Knowledge provider 的空实现或 stub
- [ ] 4.2 为后续 provider 预留 metadata 和 observability 字段

## 5. Verification

- [ ] 5.1 新增单元测试：provider 合并顺序、裁剪策略、空 provider 行为
- [ ] 5.2 新增集成测试：带 `conversation_id` 的请求可把最近会话历史注入运行时上下文
- [ ] 5.3 运行受影响测试并记录结果```

## openspec/changes/agent-runtime-context-builder/specs/agent-runtime-context-builder/spec.md

- Source: openspec/changes/agent-runtime-context-builder/specs/agent-runtime-context-builder/spec.md
- Lines: 1-40
- SHA256: 5f3cfa27b394d230bfdffd6acadfda585aacb7aeb5a51b68fc08fba8d5357bc5

```md
## NEW Requirements

### Requirement: Agent Runtime SHALL build context through a unified Context Builder
Agent Runtime SHALL collect runtime context through a single builder pipeline instead of assembling prompt context independently inside routes, nodes, or factories.

#### Scenario: build context for a conversation request
- **WHEN** a chat request includes `conversation_id`, `agent_id`, and user message text
- **THEN** the runtime SHALL create a `ContextRequest` and pass it through the Context Builder before invoking the agent or graph

#### Scenario: no provider data available
- **WHEN** no provider returns any context fragments
- **THEN** the runtime SHALL still produce a valid empty `AgentContext` and continue handling the request

### Requirement: Session history SHALL be reusable runtime context
The builder SHALL include a session provider that loads conversation history from persisted chat messages and converts it into reusable runtime context.

#### Scenario: recent messages are injected
- **WHEN** persisted messages exist for the current `conversation_id`
- **THEN** the builder SHALL load the most recent configured messages and include them in the resulting `AgentContext`

#### Scenario: internal messages are filtered
- **WHEN** history includes internal ReAct/system-only messages or non-user-visible tool noise
- **THEN** those entries SHALL be excluded from the injected session context

### Requirement: Context fragments SHALL be merged by priority and budget
The builder SHALL merge provider fragments using a stable priority order and enforce a configurable token budget.

#### Scenario: budget exceeded
- **WHEN** combined fragments exceed the configured max token budget
- **THEN** the assembler SHALL trim lower-priority or older content before producing the final rendered context

#### Scenario: session has higher priority than stubs
- **WHEN** session fragments and placeholder file/memory/knowledge fragments are both available
- **THEN** session fragments SHALL be retained ahead of lower-priority providers

### Requirement: Future providers SHALL plug into the same contract
Files, Memory, and Knowledge sources SHALL integrate through the same provider interface even if their first implementation is a stub.

#### Scenario: disabled provider
- **WHEN** a provider is configured but has no runtime source yet
- **THEN** it SHALL return an empty fragment list without breaking the builder pipeline```

