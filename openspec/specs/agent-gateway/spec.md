# agent-gateway Specification

## Purpose
TBD - created by archiving change ai-chat-layer-rewrite. Update Purpose after archive.
## Requirements
### Requirement: Agent CRUD Proxy
Spring Boot SHALL provide Agent CRUD REST API via a layered architecture (AgentClient → AgentService → AgentController) that proxies to the Python AI Service with proper logging, error handling, and DTO mapping.

#### Scenario: List all agents
- **WHEN** frontend calls `GET /api/agents`
- **THEN** AgentController delegates to AgentService, which calls AgentClient to forward to Python `GET /api/v1/agents/`, returning the agent list as typed DTOs

#### Scenario: Get agent by id
- **WHEN** frontend calls `GET /api/agents/{id}`
- **THEN** AgentController delegates to AgentService, which calls AgentClient to forward to Python `GET /api/v1/agents/{id}`, returning the agent as a typed DTO

#### Scenario: Create agent
- **WHEN** frontend calls `POST /api/agents` with agent JSON
- **THEN** AgentController validates the request DTO, AgentService logs the operation, AgentClient forwards to Python `POST /api/v1/agents/`, returning the created agent

#### Scenario: Update agent
- **WHEN** frontend calls `PUT /api/agents/{id}` with update data
- **THEN** AgentController validates the request DTO, AgentService logs the operation, AgentClient forwards to Python `PUT /api/v1/agents/{id}`, returning the updated agent

#### Scenario: Delete agent
- **WHEN** frontend calls `DELETE /api/agents/{id}`
- **THEN** AgentController delegates to AgentService, which calls AgentClient to forward to Python `DELETE /api/v1/agents/{id}`, returning the delete result

#### Scenario: Python service unavailable
- **WHEN** AgentClient calls Python service and receives a connection error
- **THEN** AgentService catches the exception and returns a 503 error with a descriptive message

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

### Requirement: Layered Architecture
Spring Boot Agent module SHALL use a three-layer architecture: Controller (endpoints) → Service (logging/error handling) → Client (WebClient to Python).

#### Scenario: AgentClient encapsulates HTTP communication
- **WHEN** AgentService needs to call the Python AI Service
- **THEN** it uses AgentClient which encapsulates WebClient configuration, base URL, and error handling

#### Scenario: AgentService handles cross-cutting concerns
- **WHEN** any agent operation is performed
- **THEN** AgentService logs the operation, handles WebClient exceptions, and maps between DTOs and Python JSON

