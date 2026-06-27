# chat-message-protocol Specification

## Purpose
TBD - created by archiving change ai-chat-layer-rewrite. Update Purpose after archive.
## Requirements
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

