# agent-chat-routing Specification

## Purpose
TBD - created by archiving change ai-chat-layer-rewrite. Update Purpose after archive.
## Requirements
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

