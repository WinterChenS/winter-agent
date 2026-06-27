# Comet Design Handoff

- Change: ai-chat-layer-rewrite
- Phase: design
- Mode: compact
- Context hash: b9abe250d24193e86562bc79b7146a88018b907f29850389abe7419afbef91a9

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/ai-chat-layer-rewrite/proposal.md

- Source: openspec/changes/ai-chat-layer-rewrite/proposal.md
- Lines: 1-36
- SHA256: f4156ea07fd7100abc385d6ab9a56fd61217a149997b7ad457dcdf0e8c90fb1c

```md
## Why

当前聊天界面存在三个层面的技术债：消息模型混杂（role 包含 `tool_summary`/`agent_step`/`thinking` 等非标准角色）、SSE 事件协议私有化（`token`/`tool_start`/`tool_result` 命名不规范）、Chat UI 代码巨石化（ChatMessage.tsx 500+ 行杂糅所有渲染逻辑）。这些问题导致：新功能叠加困难、前后端协议耦合松散、与业界 AI Chat 标准交互体验差距大。本次改造以标准化 Message Model 和 SSE 协议为核心，建立可持续演进的 AI Chat UI 专用层。

## What Changes

- **BREAKING**: 重构前端 Message 模型，role 统一为 `user` | `assistant` | `system`，新增 `reasoning`、`toolCalls`、`status`、`agentId` 字段
- **BREAKING**: SSE 事件协议重命名为 `message.delta`、`message.tool_call`、`message.reasoning`、`message.done`
- 前端新增 `/src/features/ai-chat/` 独立模块，完全自定义 Chat UI（不再使用 Ant Design 聊天组件）
- 引入 Zustand 状态管理替代散落的 useState，支持流式高频更新
- 升级代码高亮为 Shiki，替换 highlight.js
- 新增 MessageList 虚拟滚动，支持 1000+ 消息量级
- 新增 Agent 选择器（Chat Header 左侧），支持动态多 Agent 切换
- Spring Boot 新增 `/api/agents` CRUD 代理接口，新增 agentId 透传
- Python AI Service 的 GenerateRequest 新增 agentId 字段，支持 Agent 路由
- 消息历史持久化到数据库统一管理

## Capabilities

### New Capabilities
- `chat-message-protocol`: 统一前后端 Message Model（标准 role + reasoning + toolCalls + status + agentId）
- `sse-event-protocol`: 标准化 SSE 事件协议（message.delta / message.tool_call / message.reasoning / message.done）
- `ai-chat-ui`: 独立 AI Chat UI 模块（MessageBubble / ReasoningPanel / ToolCallPanel / MarkdownRenderer / 虚拟滚动 / Shiki 代码高亮）
- `agent-gateway`: Spring Boot Agent CRUD 代理 + agentId 透传 + Agent 路由
- `agent-chat-routing`: Python AI Service 根据 agentId 路由不同 Agent，输出符合新 Message Model 的 SSE 事件

### Modified Capabilities
<!-- 本次不修改已有 spec（现有 spec 均为工具系统相关，不影响） -->

## Impact

- **前端**: `src/types/chat.ts` 完全重写；`src/pages/ChatInterface.tsx` 替换为新的 ChatContainer；`src/components/ChatMessage.tsx` 拆分为多个独立组件；新增 Zustand store
- **后端**: `ChatRequest.java` 新增 agentId；`ChatController.java` 新增 Agent CRUD 端点；`AIClient.java` 透传 agentId
- **Python**: `GenerateRequest` schema 新增 agentId；`chat.py` 新增 agent 路由逻辑；`event_envelope.py` 新增 message.delta/message.tool_call/message.reasoning/message.done 事件类型
- **数据库**: 新增消息历史持久化表（复用 PostgreSQL）
- **依赖**: 前端新增 zustand、shiki、@tanstack/react-virtual；Python 无新依赖
```

## openspec/changes/ai-chat-layer-rewrite/design.md

- Source: openspec/changes/ai-chat-layer-rewrite/design.md
- Lines: 1-120
- SHA256: 22ea75f54b11778278e4cab12fa322aa54aaaee1c6e93af02c85230db2b72b00

[TRUNCATED]

```md
## Context

当前系统采用三层架构：React 前端 (Tailwind CSS + Ant Design) → Spring Boot WebFlux 网关 → Python FastAPI LangGraph AI 服务。Chat 交互的 Message 模型、SSE 协议和 UI 组件均为早期快速迭代产物，缺乏标准化设计。本次改造在不改变整体架构定位的前提下，对 Chat 专用层进行标准化升级。

## Goals / Non-Goals

**Goals:**
- 建立跨三层统一的 Message Model（TypeScript + Java + Python）
- 标准化 SSE 事件协议为 `message.delta` / `message.tool_call` / `message.reasoning` / `message.done`
- 前端 Chat UI 模块化拆分（MessageBubble / ReasoningPanel / ToolCallPanel / MarkdownRenderer / 虚拟滚动）
- Agent 选择器支持动态多 Agent 切换，消息标注处理 Agent 身份
- Spring Boot 新增 Agent CRUD 代理 + agentId 透传
- Python GenerateRequest 新增 agentId，支持 graph 内 Agent 路由
- 消息历史持久化到 PostgreSQL，前端从 DB 加载完整历史（含 reasoning/toolCalls）

**Non-Goals:**
- 不改变 LangGraph 图拓扑核心逻辑（Router/Factory/Collaboration 策略不变）
- 不重写 AdminAgents 管理页面（保留 Ant Design）
- 不引入 WebSocket（保持 SSE）
- 不改变用户认证体系

## Decisions

### 1. 前端状态管理：Zustand

**选择**: Zustand，配合 `subscribeWithSelector` 中间件
**理由**: 
- 相比 Redux：API 简洁，无需 action creator/reducer 模板代码，bundle 体积小 (~1KB)
- 相比 Context：选择器级别的精准重渲染，避免流式更新时的整树 re-render
- 内置 `persist` 中间件可用于会话状态恢复
**备选**: Jotai（atom 粒度更细但流式场景下需更多 atom 协调）、Redux Toolkit（过度工程化）

### 2. 代码高亮：Shiki

**选择**: Shiki (通过 `shiki` npm 包，CDN 按需加载主题/语言)
**理由**:
- 语法准确度高于 highlight.js（基于 TextMate grammar，与 VS Code 一致）
- 支持 VS Code 主题生态
- 服务端/构建时可预编译，减少前端运行时开销
**风险**: 包体积大 (~10MB+) → **缓解**: 使用 `@shikijs/core` + 按需加载语言/主题；考虑构建时 tree-shake

### 3. 虚拟滚动：@tanstack/react-virtual

**选择**: `@tanstack/react-virtual`
**理由**: TanStack 生态成熟，支持动态高度行（消息气泡高度不一），API 简洁
**备选**: react-window（不支持动态高度）、react-virtuoso（功能全但 API 复杂）

### 4. SSE 事件协议升级策略

**选择**: **直接重命名，不做兼容过渡**
**理由**: 
- 当前系统仅内部使用，无外部消费者
- 旧事件命名（`token`/`tool_start`/`tool_result`）与新命名差异大，兼容过渡增加复杂度
- 前后端同时升级，一次性切换

**新事件映射**:
| 旧事件 | 新事件 | payload 变更 |
|--------|--------|-------------|
| `token` | `message.delta` | 新增 `messageId` 字段 |
| `tool_start` + `tool_result` | `message.tool_call` (合并) | 统一 `ToolCall { name, arguments, status, result }` |
| `reasoning_delta` / `thought` | `message.reasoning` | 标准化 payload |
| 流结束信号 (隐式) | `message.done` | `{ messageId, status: "done" }` |
| `tool_summary` | **废弃**（内嵌到 message.tool_call） | - |
| `agent_step` | **废弃**（合并到 message.delta 的 metadata） | - |
| `error` | **保留**，增加 `messageId` | 新增 `messageId` |

### 5. 消息持久化方案

**选择**: 复用 PostgreSQL（Python 端已有 checkpointer），新增 `chat_messages` 表
**Schema**:
```sql
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY,
  conversation_id UUID NOT NULL,
  role VARCHAR(16) NOT NULL,           -- user | assistant | system
  content TEXT NOT NULL DEFAULT '',
  reasoning TEXT,                       -- JSON: reasoning content
  tool_calls JSONB,                     -- JSON: ToolCall[]
  status VARCHAR(16) DEFAULT 'done',   -- streaming | done | error
  agent_id VARCHAR(64),
```

Full source: openspec/changes/ai-chat-layer-rewrite/design.md

## openspec/changes/ai-chat-layer-rewrite/tasks.md

- Source: openspec/changes/ai-chat-layer-rewrite/tasks.md
- Lines: 1-54
- SHA256: 38c59db6f161da8288f1ea606a798006a0b3ca79813664abcfb987ee02511d60

```md
## 1. Python AI Service — 协议层升级

- [ ] 1.1 重构 `domain/event_envelope.py`：新增 `envelope_message_delta`、`envelope_message_tool_call`、`envelope_message_reasoning`、`envelope_message_done` 事件构建函数，保留 `envelope_error`
- [ ] 1.2 更新 `api/events/event_mapper.py`：将 LangGraph 事件映射改为新协议（token → message.delta, tool_start/tool_result → message.tool_call, reasoning_delta → message.reasoning），为每个事件添加 `messageId` 和 `agentId`
- [ ] 1.3 更新 `api/schemas.py`：`GenerateRequest` 新增 `agentId?: str` 字段
- [ ] 1.4 更新 `api/routes/chat.py`：`stream_generate` 根据 agentId 加载 Agent 定义并注入 `active_agent`；在流开始时生成 messageId；在流结束时发送 `message.done`
- [ ] 1.5 新增 `db/chat_message_repository.py`：实现 `chat_messages` 表的 CRUD（create/update/getByConversation）
- [ ] 1.6 新增 PostgreSQL 迁移脚本：创建 `chat_messages` 表
- [ ] 1.7 更新 `api/routes/chat.py` 的 `get_chat_history`：返回新 Message Model 格式（含 reasoning/toolCalls/agentId/status）

## 2. Python AI Service — Agent 路由增强

- [ ] 2.1 更新 `graph/graph.py`：在 graph state 初始化时读取 `active_agent` 字段，支持按 agentId 选择对应 Agent Node
- [ ] 2.2 验证 RouterAgent 在收到 active_agent 时直接路由到对应 Agent（不经过关键词匹配）

## 3. Spring Boot — Agent 网关

- [ ] 3.1 新增 `AgentController.java`：实现 `GET/POST/PUT/DELETE /api/agents`，代理转发到 Python `/api/v1/agents/`
- [ ] 3.2 更新 `ChatRequest.java`：新增 `agentId` 字段
- [ ] 3.3 更新 `AIClient.java`：`streamGenerate` 方法透传 agentId 到 Python

## 4. 前端 — 类型与基础设施

- [ ] 4.1 重写 `frontend/src/types/chat.ts`：使用新 Message/ToolCall 类型定义（role 为 user|assistant|system，新增 reasoning/toolCalls/status/agentId）
- [ ] 4.2 安装依赖：`zustand`、`@tanstack/react-virtual`、`shiki`
- [ ] 4.3 新增 `frontend/src/features/ai-chat/types/message.ts`：导出 Message、ToolCall 类型
- [ ] 4.4 新增 `frontend/src/features/ai-chat/store/chatStore.ts`：Zustand store（messages, addMessage, updateMessage, appendDelta, upsertToolCall, appendReasoning, setMessageStatus, agentId, setAgentId, conversationId）
- [ ] 4.5 新增 `frontend/src/features/ai-chat/services/chatApi.ts`：封装 SSE fetch 请求（POST /api/chat，含 agentId），解析新事件协议（message.delta/tool_call/reasoning/done）

## 5. 前端 — 核心组件

- [ ] 5.1 新增 `ChatContainer.tsx`：顶层布局（Header + MessageList + InputBox），集成 Agent 选择器
- [ ] 5.2 新增 `MessageList.tsx`：使用 `@tanstack/react-virtual` 实现虚拟滚动，自动滚动/用户覆盖逻辑
- [ ] 5.3 新增 `MessageBubble.tsx`：用户右对齐蓝色气泡，AI 左对齐灰色气泡，显示 Agent 标识，渲染 Markdown + 图表
- [ ] 5.4 新增 `ReasoningPanel.tsx`：可折叠推理面板，支持 Markdown 渲染
- [ ] 5.5 新增 `ToolCallPanel.tsx`：可折叠工具调用卡片（工具名 + 参数 + 状态图标 + 结果详情，支持 running/done/failed 三态动画）
- [ ] 5.6 新增 `MarkdownRenderer.tsx`：集成 react-markdown + Shiki 代码高亮 + LaTeX 支持 + 表格/引用渲染
- [ ] 5.7 新增 `StreamingRenderer.tsx`：流式内容渲染容器（增量渲染、闪烁光标动画）
- [ ] 5.8 新增 `InputBox.tsx`：文本输入框 + 发送按钮 + loading 状态禁用

## 6. 前端 — 集成与迁移

- [ ] 6.1 新增 `frontend/src/features/ai-chat/hooks/useChatStream.ts`：基于 chatStore + chatApi 的流式对话 hook
- [ ] 6.2 新增 `frontend/src/features/ai-chat/hooks/useConversation.ts`：会话管理 hook（加载历史、创建会话）
- [ ] 6.3 更新 `App.tsx` 路由：Chat 页面路由指向新 ChatContainer
- [ ] 6.4 废弃旧 ChatMessage.tsx / ChatInput.tsx / useChat.ts（保留文件不删，移除路由引用）
- [ ] 6.5 清理旧的 MessageList.tsx 引用

## 7. 测试与验证

- [ ] 7.1 更新 `scripts/test_chat_scenarios.py`：适配新 SSE 事件协议
- [ ] 7.2 编写前端单元测试：chatStore actions（addMessage/updateMessage/appendDelta 等）
- [ ] 7.3 E2E 测试：Agent 选择 → 发送消息 → 流式接收 → 消息完成全链路
- [ ] 7.4 验收检查：对照验收标准逐项确认
```

## openspec/changes/ai-chat-layer-rewrite/specs/agent-chat-routing/spec.md

- Source: openspec/changes/ai-chat-layer-rewrite/specs/agent-chat-routing/spec.md
- Lines: 1-50
- SHA256: a139b31d51a419b6ea08fd06c9d66f4e0b0c51fd4ca78b2e69184bb4cf67dce6

```md
# Agent Chat Routing

Python AI Service 根据 agentId 路由不同 Agent，输出标准化 SSE 事件。

## ADDED Requirements

### Requirement: AgentId-Based Routing
Python AI Service SHALL 根据请求中的 agentId 从 Agent Repository 加载 Agent 定义，并将其注入 LangGraph state 的 `active_agent` 字段。

#### Scenario: Request with valid agentId
- **WHEN** 收到 `POST /chat` 请求携带 `agentId: "search-agent"`
- **THEN** 系统从数据库加载 Search Agent 定义，注入 `active_agent` 到 graph state，RouterAgent 据此路由

#### Scenario: Request without agentId
- **WHEN** 收到 `POST /chat` 请求未携带 agentId
- **THEN** 系统使用默认 Agent（或 RouterAgent 自动匹配）

#### Scenario: Request with invalid agentId
- **WHEN** 收到 `POST /chat` 请求携带不存在的 agentId
- **THEN** 系统返回 error 事件：`{ type: "message.done", status: "error", error: "Agent not found: xxx" }`

### Requirement: Standardized SSE Event Output
Python AI Service SHALL 输出符合新协议标准的 SSE 事件：`message.delta`、`message.tool_call`、`message.reasoning`、`message.done`。

#### Scenario: Token streaming event
- **WHEN** LLM 生成 token
- **THEN** 系统发送 `message.delta` 事件：`{ type: "message.delta", messageId, agentId, delta: "xxx" }`

#### Scenario: Tool call event
- **WHEN** Agent 调用工具
- **THEN** 系统发送 `message.tool_call` 事件：`{ type: "message.tool_call", messageId, agentId, toolCall: { name, arguments, status } }`

#### Scenario: Reasoning event
- **WHEN** LLM 输出 reasoning/thinking token
- **THEN** 系统发送 `message.reasoning` 事件：`{ type: "message.reasoning", messageId, agentId, delta: "xxx" }`

#### Scenario: Stream completion event
- **WHEN** Agent 完成全部输出
- **THEN** 系统发送 `message.done` 事件：`{ type: "message.done", messageId, status: "done" }`

### Requirement: Message Persistence in AI Service
Python AI Service SHALL 在每条消息完成（status 变为 "done"）后异步写入 PostgreSQL chat_messages 表。

#### Scenario: Save completed message
- **WHEN** Agent 完成回复（发送 message.done 后）
- **THEN** 系统异步将完整 Message 写入数据库，包含 id、conversation_id、role、content、reasoning、tool_calls、status、agent_id、created_at

#### Scenario: Save error message
- **WHEN** Agent 回复出错（发送 message.done status: "error" 后）
- **THEN** 系统将错误消息写入数据库，status 为 "error"
```

## openspec/changes/ai-chat-layer-rewrite/specs/agent-gateway/spec.md

- Source: openspec/changes/ai-chat-layer-rewrite/specs/agent-gateway/spec.md
- Lines: 1-38
- SHA256: aa3b7a7dc9fd881639bc4e9e290379dc28746fae646c91f35b74709cf505d730

```md
# Agent Gateway

Spring Boot 网关层 Agent CRUD 代理与 agentId 透传。

## ADDED Requirements

### Requirement: Agent CRUD Proxy
Spring Boot SHALL 提供 Agent CRUD REST API，代理转发到 Python AI Service。

#### Scenario: List all agents
- **WHEN** 前端请求 `GET /api/agents`
- **THEN** Spring Boot 转发到 Python `GET /api/v1/agents/`，返回 Agent 列表（过滤敏感字段如 system_prompt 的完整内容）

#### Scenario: Create agent
- **WHEN** 前端请求 `POST /api/agents` 携带 Agent JSON
- **THEN** Spring Boot 转发到 Python `POST /api/v1/agents/`，返回创建的 Agent

#### Scenario: Update agent
- **WHEN** 前端请求 `PUT /api/agents/{id}` 携带更新数据
- **THEN** Spring Boot 转发到 Python `PUT /api/v1/agents/{id}`，返回更新后的 Agent

#### Scenario: Delete agent
- **WHEN** 前端请求 `DELETE /api/agents/{id}`
- **THEN** Spring Boot 转发到 Python `DELETE /api/v1/agents/{id}`，返回删除结果

### Requirement: AgentId Passthrough in Chat
Spring Boot ChatController SHALL 接收请求中的 agentId 字段并透传到 Python AI Service。

#### Scenario: Chat request with agentId
- **WHEN** 前端发送 `POST /api/chat` 包含 `{ message, agentId, conversationId }`
- **THEN** Spring Boot 将 agentId 透传到 Python `POST /api/v1/generate/stream`

### Requirement: SSE Passthrough
Spring Boot SHALL 将 Python AI Service 的 SSE 事件流原样透传给前端，不做解析或转换。

#### Scenario: Transparent SSE forwarding
- **WHEN** Python 返回 SSE 事件流
- **THEN** Spring Boot 原样转发每个事件到前端，保持 `Content-Type: text/event-stream`
```

## openspec/changes/ai-chat-layer-rewrite/specs/ai-chat-ui/spec.md

- Source: openspec/changes/ai-chat-layer-rewrite/specs/ai-chat-ui/spec.md
- Lines: 1-107
- SHA256: c563b2d6bfaa279ace48cc6c1306f681e654152824435b2d9f6e70c01b033f41

[TRUNCATED]

```md
# AI Chat UI

独立 AI Chat UI 模块，完全自定义渲染，不使用 Ant Design 聊天组件。

## ADDED Requirements

### Requirement: ChatContainer Layout
系统 SHALL 提供 ChatContainer 作为聊天界面的顶层容器，包含 Header（Agent 选择器 + 会话信息）、MessageList（消息列表）、InputBox（输入区域）三个区域。

#### Scenario: Chat page layout
- **WHEN** 用户进入聊天页面
- **THEN** 页面展示 Header（顶部）、MessageList（中间填充）、InputBox（底部固定）三区域布局

### Requirement: Agent Selector
系统 SHALL 在 Chat Header 提供 Agent 下拉选择器，支持切换当前对话的 Agent。

#### Scenario: Select an agent
- **WHEN** 用户从 Agent 选择器中选择一个 Agent
- **THEN** 后续消息携带该 agentId，消息气泡中显示 Agent 标识

#### Scenario: Filter disabled agents
- **WHEN** 某些 Agent 被禁用（enabled: false）
- **THEN** 这些 Agent 不在选择器中显示

#### Scenario: Agent identity in message
- **WHEN** AI 回复由特定 Agent 处理
- **THEN** 该消息气泡显示 Agent 名称/标识（如 "🔍 Search Agent"）

### Requirement: MessageBubble
系统 SHALL 提供 MessageBubble 组件，根据 role 渲染不同样式：用户消息右对齐蓝色气泡，AI 消息左对齐灰色气泡。

#### Scenario: User message bubble
- **WHEN** 渲染 role 为 "user" 的消息
- **THEN** 气泡右对齐，蓝色背景，显示 content 纯文本

#### Scenario: Assistant message bubble
- **WHEN** 渲染 role 为 "assistant" 的消息
- **THEN** 气泡左对齐，灰色/白色背景，显示 Markdown 渲染后的 content

### Requirement: ReasoningPanel
系统 SHALL 提供 ReasoningPanel 组件，以可折叠面板展示 AI 的思考过程（reasoning 字段）。

#### Scenario: Collapsed reasoning display
- **WHEN** 消息包含 reasoning 且面板折叠
- **THEN** 显示"思考过程 (N 步)"标题，点击可展开

#### Scenario: Expanded reasoning display
- **WHEN** 用户点击展开推理面板
- **THEN** 展示完整的推理内容，支持 Markdown 渲染

### Requirement: ToolCallPanel
系统 SHALL 提供 ToolCallPanel 组件，以可折叠卡片展示工具调用详情（工具名、参数、执行状态、结果）。

#### Scenario: Running tool display
- **WHEN** 工具调用状态为 "running"
- **THEN** 显示工具名称 + 旋转加载动画

#### Scenario: Completed tool display
- **WHEN** 工具调用状态为 "done"
- **THEN** 显示工具名称 + 绿色完成标记 + 可展开查看结果详情

#### Scenario: Failed tool display
- **WHEN** 工具调用状态为 "failed"
- **THEN** 显示工具名称 + 红色失败标记 + 错误信息

### Requirement: Markdown Renderer
系统 SHALL 提供 Markdown 渲染组件，支持：段落、列表、表格、代码块（Shiki 高亮）、LaTeX 公式、引用块。

#### Scenario: Code block with syntax highlighting
- **WHEN** Markdown 包含代码块
- **THEN** 使用 Shiki 进行语法高亮，显示行号和复制按钮

#### Scenario: Table rendering
- **WHEN** Markdown 包含表格
- **THEN** 渲染带边框和斑马纹的表格，横向溢出时滚动

### Requirement: Virtual Scrolling
系统 SHALL 使用 @tanstack/react-virtual 实现 MessageList 虚拟滚动，支持 1000+ 消息的流畅渲染。

#### Scenario: Long conversation performance
```

Full source: openspec/changes/ai-chat-layer-rewrite/specs/ai-chat-ui/spec.md

## openspec/changes/ai-chat-layer-rewrite/specs/chat-message-protocol/spec.md

- Source: openspec/changes/ai-chat-layer-rewrite/specs/chat-message-protocol/spec.md
- Lines: 1-59
- SHA256: 150a74d0ff85f484c6c076c1dccf25fe68ce49f61c465be8e9f82220f799ac4e

```md
# Chat Message Protocol

统一前后端三层（TypeScript / Java / Python）的 Message Model 定义。

## ADDED Requirements

### Requirement: Standard Message Model
系统 SHALL 使用统一的 Message 数据结构，包含以下字段：
- `id: string` — 消息唯一标识（UUID）
- `role: "user" | "assistant" | "system"` — 消息角色
- `content: string` — 消息正文
- `reasoning?: string` — AI 思考过程（可选）
- `toolCalls?: ToolCall[]` — 工具调用列表（可选）
- `status: "streaming" | "done" | "error"` — 消息状态
- `agentId?: string` — 处理该消息的 Agent 标识
- `conversationId?: string` — 所属会话标识
- `createdAt?: number` — 创建时间戳（毫秒）

#### Scenario: User message creation
- **WHEN** 用户发送一条消息
- **THEN** 系统创建 Message 对象，role 为 "user"，status 为 "done"

#### Scenario: Assistant message streaming
- **WHEN** AI 开始流式回复
- **THEN** 系统创建 Message 对象，role 为 "assistant"，status 为 "streaming"，content 初始为空字符串

#### Scenario: Assistant message completion
- **WHEN** AI 完成流式回复
- **THEN** 系统将 status 更新为 "done"，保存最终 content

#### Scenario: Message with reasoning
- **WHEN** AI 在回复前进行思考
- **THEN** 系统将思考过程写入 reasoning 字段，最终消息同时包含 reasoning 和 content

### Requirement: ToolCall Model
系统 SHALL 使用统一的 ToolCall 数据结构：
- `name: string` — 工具名称
- `arguments: any` — 工具调用参数
- `status?: "pending" | "running" | "done" | "failed"` — 执行状态
- `result?: any` — 工具返回结果

#### Scenario: Tool call lifecycle
- **WHEN** AI 调用一个工具
- **THEN** 系统创建 ToolCall 对象（status: "pending"），执行过程中更新为 "running"，完成后更新为 "done" 并填充 result

#### Scenario: Failed tool call
- **WHEN** 工具执行失败
- **THEN** 系统将 ToolCall status 设为 "failed"，result 包含错误信息

### Requirement: Message Persistence
系统 SHALL 将消息持久化到 PostgreSQL 数据库。

#### Scenario: Save message to database
- **WHEN** 一条消息完成（status: "done" 或 "error"）
- **THEN** 系统将其写入 chat_messages 表，包含所有字段

#### Scenario: Load history from database
- **WHEN** 用户进入已有会话
- **THEN** 系统从数据库按 conversation_id 加载历史消息，按 created_at 排序
```

## openspec/changes/ai-chat-layer-rewrite/specs/sse-event-protocol/spec.md

- Source: openspec/changes/ai-chat-layer-rewrite/specs/sse-event-protocol/spec.md
- Lines: 1-97
- SHA256: fff614e81d3d647ff067acae99459964b35adbda8f989d32e4d8b4758d79a9c6

[TRUNCATED]

```md
# SSE Event Protocol

标准化前后端流式通信的 SSE 事件协议。

## ADDED Requirements

### Requirement: message.delta Event
系统 SHALL 使用 `message.delta` 事件传输 token 级别的文本增量。

事件格式：
```json
{
  "type": "message.delta",
  "messageId": "uuid",
  "agentId": "agent-001",
  "delta": "文本增量"
}
```

#### Scenario: Token-level streaming
- **WHEN** AI 生成回复文本
- **THEN** 每个 token 通过 `message.delta` 事件发送，前端增量渲染

#### Scenario: Multi-message delta routing
- **WHEN** 流式响应包含多个工具调用结果
- **THEN** 每个 `message.delta` 事件携带 `messageId` 标识归属

### Requirement: message.tool_call Event
系统 SHALL 使用 `message.tool_call` 事件传输工具调用状态。

事件格式：
```json
{
  "type": "message.tool_call",
  "messageId": "uuid",
  "agentId": "agent-001",
  "toolCall": {
    "name": "search",
    "arguments": { "query": "..." },
    "status": "running" | "done" | "failed",
    "result": "..."
  }
}
```

#### Scenario: Tool execution lifecycle via SSE
- **WHEN** AI 调用工具
- **THEN** 前端收到 `message.tool_call` 事件（status: "running"），执行完成后收到同一 toolCall 的更新事件（status: "done"）

#### Scenario: Tool call failure
- **WHEN** 工具执行失败
- **THEN** `message.tool_call` 事件 status 为 "failed"，result 包含错误信息

### Requirement: message.reasoning Event
系统 SHALL 使用 `message.reasoning` 事件传输 AI 思考过程。

事件格式：
```json
{
  "type": "message.reasoning",
  "messageId": "uuid",
  "agentId": "agent-001",
  "delta": "思考内容增量"
}
```

#### Scenario: Streaming reasoning display
- **WHEN** AI 在生成回复前进行思考
- **THEN** 前端通过 `message.reasoning` 事件收到增量思考内容，在 ReasoningPanel 中折叠展示

### Requirement: message.done Event
系统 SHALL 使用 `message.done` 事件标识消息流结束。

事件格式：
```json
{
  "type": "message.done",
  "messageId": "uuid",
  "status": "done" | "error",
  "error": "可选错误信息"
```

Full source: openspec/changes/ai-chat-layer-rewrite/specs/sse-event-protocol/spec.md

