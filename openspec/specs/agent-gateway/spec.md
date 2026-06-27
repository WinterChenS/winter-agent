# agent-gateway Specification

## Purpose
TBD - created by archiving change ai-chat-layer-rewrite. Update Purpose after archive.
## Requirements
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

