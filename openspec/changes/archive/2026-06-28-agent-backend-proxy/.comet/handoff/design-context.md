# Comet Design Handoff

- Change: agent-backend-proxy
- Phase: design
- Mode: compact
- Context hash: c331e1a62babb5c95ea96a25c7a9e6608bf9d8a635b0e0130694988e02fec0c1

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/agent-backend-proxy/proposal.md

- Source: openspec/changes/agent-backend-proxy/proposal.md
- Lines: 1-33
- SHA256: 3842e148f5962d7ae2fd7a57fe486e5440cd80f14fe457acabc665b36af33f4c

```md
## Why

当前 Agent 管理系统仅能通过直接修改数据库或配置文件来管理 Agent。虽然 Python AI Service 已有基础 CRUD API，但缺少 enable/disable 快捷操作和 clone 能力，SpringBoot 代理层仅做了裸透传，缺少 DTO 定义、异常处理和日志记录。本次变更为后续前端可视化管理页面提供完整的后端 API 基础设施。

## What Changes

- **PostgreSQL**: 新增 migration `V003__agent_upgrade.sql`，为 `agent_definitions` 表新增 9 个字段（icon, agent_type, avatar_url, is_builtin, tags, metadata, created_by, updated_by, version）
- **Python API**: Agent model 扩展支持新字段，新增 3 个端点（enable/disable/clone）
- **Python Repo**: `AgentRepository` 新增 `set_enabled()` 和 `clone()` 方法
- **SpringBoot**: 重写 `AgentController`，新增 `AgentClient`（WebClient 封装）、`AgentService`（日志/异常/转换）、完整 DTO（request/response）
- 现有聊天 SSE 流程和 Agent Runtime 不受影响

## Capabilities

### New Capabilities
- `agent-db-migration`: agent_definitions 表新增 icon/agent_type/tags/metadata 等扩展字段
- `agent-toggle-api`: Python enable/disable 端点，SpringBoot 代理透传
- `agent-clone-api`: Python clone 端点（自动追加 (Copy) 后缀），SpringBoot 代理透传

### Modified Capabilities
- `agent-gateway`: SpringBoot AgentController 从裸透传升级为带 DTO/Service/Client 分层架构

## Impact

- `ai_service/db/migrations/` — 新增 V003 SQL 文件
- `ai_service/models/agent.py` — Pydantic model 扩展
- `ai_service/repositories/agent_repository.py` — 新增 set_enabled/clone 方法
- `ai_service/api/routes/agents.py` — 新增 3 端点
- `backend/.../controller/AgentController.java` — 重写
- `backend/.../service/AgentService.java` — 新增
- `backend/.../client/AgentClient.java` — 新增
- `backend/.../dto/` — 新增 DTO 类
- `backend/.../config/` — 可能新增 AgentConfig
```

## openspec/changes/agent-backend-proxy/design.md

- Source: openspec/changes/agent-backend-proxy/design.md
- Lines: 1-54
- SHA256: 62a6e52be8b3c1b20a7997f5d9c41fb3292288355cf1f6dafce1a154155a4272

```md
## Context

当前 SpringBoot Agent 模块仅有一个 `AgentController` 做裸透传（raw String 入参/出参，无 DTO、无 Service、无错误处理）。Python AI Service 已有 Agent CRUD API，但缺少 enable/disable toggle 和 clone 端点。数据库 `agent_definitions` 表缺少扩展字段（icon、tags、metadata 等）支撑可视化管理。

## Goals / Non-Goals

**Goals:**
- 为 `agent_definitions` 表新增 9 个扩展字段
- Python 新增 enable/disable/clone 端点
- SpringBoot 建立三层架构：Controller → Service → Client
- SpringBoot 新增完整的 DTO 和错误处理
- 所有新端点通过 JWT 鉴权

**Non-Goals:**
- 不修改 Agent Runtime / Graph 执行 / SSE 流程
- 不修改 `model_config` JSONB 字段结构
- 不做前端改动

## Decisions

### Decision 1: SpringBoot 三层架构
**选择**: Controller → Service → Client（WebClient 封装）
**理由**: 当前 AgentController 直接注入 WebClient 做裸透传，无错误处理、无日志、无类型安全。引入 Service 层处理日志和异常转换，Client 层封装 HTTP 通信，Controller 只做端点声明和 DTO 校验。
**备选**: 保持当前薄透传模式 — 拒绝，因为需要统一的错误处理和日志。

### Decision 2: AgentClient 设计
**选择**: 独立 `AgentClient` 组件（`@Component`），注入 `@Value("${aichat.ai-service-url}")` 作为 baseUrl
**理由**: 与现有 `AIClient` 模式一致（已有 WebClient bean 配置 16MB buffer），但独立封装 Agent 相关端点。
**备选**: 扩展现有 `AIClient` — 拒绝，职责不同（Chat vs Agent 管理），分开更清晰。

### Decision 3: Python Clone 命名策略
**选择**: `display_name` 追加 ` (Copy)`，`name` 追加 `-copy`（若冲突则追加数字后缀）
**理由**: 简单直观，用户可在前端自行修改。

### Decision 4: DB Migration 字段设计
**选择**: `icon`/`agent_type`/`tags` 等字段直接新增列，`model_name`/`temperature`/`top_p`/`max_tokens` 保持在 `model_config` JSONB 中
**理由**: 用户确认 model 参数统一放在 model_config 中，避免字段冗余。

### Decision 5: created_by / updated_by 来源
**选择**: 从 SpringBoot 层获取当前登录用户名（JWT token 中提取），透传到 Python
**理由**: Python 层无认证（被 SpringBoot 网关隔离），用户身份由 SpringBoot 提供。

## Risks / Trade-offs

- **[Risk] Migration 回滚复杂** → Migration 写入 `V003__agent_upgrade.sql`，遵循 Flyway 命名规范。新增列均为可空或有默认值，不影响现有数据。
- **[Risk] clone 在 Python 执行时可能阻塞** → clone 只是 INSERT 操作，非耗时操作，同步返回即可。
- **[Risk] enable/disable 后 Agent 列表缓存不一致** → 当前无缓存层，每次查询直接读数据库，无需担心。

## Migration Plan

1. 部署 Python 代码更新（model 扩展 + 新端点）
2. 执行 `V003__agent_upgrade.sql` migration
3. 部署 SpringBoot 代码更新
4. 无 downtime 风险 — 仅新增列和新增端点
```

## openspec/changes/agent-backend-proxy/tasks.md

- Source: openspec/changes/agent-backend-proxy/tasks.md
- Lines: 1-45
- SHA256: 1de768808dbb36de2c668b85e8a2281be177c0d052bbd2a41f3d7df611010711

```md
## 1. DB Migration

- [ ] 1.1 Create `V003__agent_upgrade.sql` with 9 new columns (icon, agent_type, avatar_url, is_builtin, tags, metadata, created_by, updated_by, version)
- [ ] 1.2 Add backfill SQL for existing seed agents (is_builtin = true)

## 2. Python Agent Model & Repository Enhancement

- [ ] 2.1 Extend `AgentDefinition` Pydantic model with new fields (icon, agent_type, avatar_url, is_builtin, tags, metadata, created_by, updated_by, version)
- [ ] 2.2 Add `set_enabled(agent_id, enabled)` method to `AgentRepository` base and `PostgresAgentRepository`
- [ ] 2.3 Add `clone(agent_id)` method to `AgentRepository` base and `PostgresAgentRepository`
- [ ] 2.4 Update `_row_to_agent()` and `create()`/`update()` to handle new fields

## 3. Python Agent API Endpoints

- [ ] 3.1 Add `POST /api/v1/agents/{id}/enable` endpoint
- [ ] 3.2 Add `POST /api/v1/agents/{id}/disable` endpoint
- [ ] 3.3 Add `POST /api/v1/agents/{id}/clone` endpoint (display_name append " (Copy)", name append "-copy")

## 4. SpringBoot DTOs

- [ ] 4.1 Create `AgentRequest` record (input DTO with validation annotations)
- [ ] 4.2 Create `AgentResponse` record (output DTO mapping all agent fields)

## 5. SpringBoot AgentClient

- [ ] 5.1 Create `AgentClient` component with WebClient methods: listAll, getById, create, update, delete, enable, disable, clone
- [ ] 5.2 Configure base URL from `aichat.ai-service-url` property

## 6. SpringBoot AgentService

- [ ] 6.1 Create `AgentService` with business logic: CRUD delegation, enable/disable, clone
- [ ] 6.2 Add logging for each operation
- [ ] 6.3 Add exception handling (connection errors → 503, 4xx/5xx propagation)

## 7. SpringBoot AgentController

- [ ] 7.1 Rewrite `AgentController` with full endpoints: GET list/detail, POST create, PUT update, DELETE delete, POST enable, POST disable, POST clone
- [ ] 7.2 Wire endpoints through `SecurityConfig` (require JWT authentication)

## 8. Verification

- [ ] 8.1 Verify migration applies cleanly and existing seed data is preserved
- [ ] 8.2 Verify Python enable/disable/clone endpoints via curl/HTTP test
- [ ] 8.3 Verify SpringBoot proxy endpoints return correct data
- [ ] 8.4 Verify existing chat SSE flow is unaffected (send a chat message)
```

## openspec/changes/agent-backend-proxy/specs/agent-clone-api/spec.md

- Source: openspec/changes/agent-backend-proxy/specs/agent-clone-api/spec.md
- Lines: 1-27
- SHA256: 39cb7193ec10a1b8b8d0291918097230ad2851147926924f3cfce436416eb5b7

```md
## ADDED Requirements

### Requirement: Clone Agent Endpoint
Python AI Service SHALL provide an endpoint to clone an existing agent definition.

#### Scenario: Clone an existing agent
- **WHEN** `POST /api/v1/agents/{id}/clone` is called
- **THEN** a new agent is created with all fields copied from the source agent, a new unique `id`, and `display_name` set to `"{original_display_name} (Copy)"`

#### Scenario: Clone with name conflict
- **WHEN** cloning would result in a duplicate `name`
- **THEN** the system appends a suffix to make the name unique (e.g., `"{name}-copy"`)

#### Scenario: Clone non-existent agent
- **WHEN** `POST /api/v1/agents/{id}/clone` is called with a non-existent id
- **THEN** a 404 error response is returned

#### Scenario: Cloned agent inherits tools and config
- **WHEN** an agent with specific tools, model_config, and collaboration_strategy is cloned
- **THEN** the cloned agent has identical tools, model_config, and collaboration_strategy

### Requirement: SpringBoot Clone Proxy
Spring Boot SHALL proxy clone requests to the Python AI Service.

#### Scenario: Proxy clone request
- **WHEN** `POST /api/agents/{id}/clone` is called
- **THEN** Spring Boot forwards to Python `POST /api/v1/agents/{id}/clone` and returns the result
```

## openspec/changes/agent-backend-proxy/specs/agent-db-migration/spec.md

- Source: openspec/changes/agent-backend-proxy/specs/agent-db-migration/spec.md
- Lines: 1-30
- SHA256: 17bf978563c1155606dbc7c925991bacd652cea9241331e8e52d8cbad8e1deb4

```md
## ADDED Requirements

### Requirement: Agent Definition Extended Schema
The `agent_definitions` table SHALL support extended metadata fields for visualization and categorization.

#### Scenario: New columns exist after migration
- **WHEN** migration V003 is applied
- **THEN** `agent_definitions` table includes columns: `icon VARCHAR(64)`, `agent_type VARCHAR(32)`, `avatar_url TEXT`, `is_builtin BOOLEAN DEFAULT false`, `tags JSONB DEFAULT '[]'`, `metadata JSONB DEFAULT '{}'`, `created_by VARCHAR`, `updated_by VARCHAR`, `version INTEGER DEFAULT 1`

#### Scenario: Existing data preserved after migration
- **WHEN** migration V003 is applied to a database with existing agents
- **THEN** all existing agent rows remain intact with new columns set to their DEFAULT values

### Requirement: Track agent creator and updater
The system SHALL track who created and last updated each agent definition.

#### Scenario: New agent records creator
- **WHEN** a new agent is created via API
- **THEN** `created_by` is set to the authenticated username and `version` is set to 1

#### Scenario: Updated agent records modifier
- **WHEN** an existing agent is updated via API
- **THEN** `updated_by` is set to the authenticated username and `version` is incremented

### Requirement: Agent builtin flag
The system SHALL distinguish built-in (seeded) agents from user-created agents.

#### Scenario: Seeded agents marked as builtin
- **WHEN** migration V003 runs
- **THEN** existing seed agents are backfilled with `is_builtin = true`
```

## openspec/changes/agent-backend-proxy/specs/agent-gateway/spec.md

- Source: openspec/changes/agent-backend-proxy/specs/agent-gateway/spec.md
- Lines: 1-41
- SHA256: 8b8ad4aff44f03550cd5858fd8e4de6204252c910bf87aa17a8ddee0989e1436

```md
## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Layered Architecture
Spring Boot Agent module SHALL use a three-layer architecture: Controller (endpoints) → Service (logging/error handling) → Client (WebClient to Python).

#### Scenario: AgentClient encapsulates HTTP communication
- **WHEN** AgentService needs to call the Python AI Service
- **THEN** it uses AgentClient which encapsulates WebClient configuration, base URL, and error handling

#### Scenario: AgentService handles cross-cutting concerns
- **WHEN** any agent operation is performed
- **THEN** AgentService logs the operation, handles WebClient exceptions, and maps between DTOs and Python JSON
```

## openspec/changes/agent-backend-proxy/specs/agent-toggle-api/spec.md

- Source: openspec/changes/agent-backend-proxy/specs/agent-toggle-api/spec.md
- Lines: 1-42
- SHA256: eed004a3116130890d73ea28f38bfabb2d3682e378e0dff1a08bb523d3108f04

```md
## ADDED Requirements

### Requirement: Enable Agent Endpoint
Python AI Service SHALL provide an endpoint to enable an agent definition.

#### Scenario: Enable a disabled agent
- **WHEN** `POST /api/v1/agents/{id}/enable` is called
- **THEN** the agent's `enabled` field is set to `true` and the updated agent is returned

#### Scenario: Enable an already enabled agent
- **WHEN** `POST /api/v1/agents/{id}/enable` is called on an already enabled agent
- **THEN** the agent is returned unchanged with `enabled: true`

#### Scenario: Enable non-existent agent
- **WHEN** `POST /api/v1/agents/{id}/enable` is called with a non-existent id
- **THEN** a 404 error response is returned

### Requirement: Disable Agent Endpoint
Python AI Service SHALL provide an endpoint to disable an agent definition.

#### Scenario: Disable an enabled agent
- **WHEN** `POST /api/v1/agents/{id}/disable` is called
- **THEN** the agent's `enabled` field is set to `false` and the updated agent is returned

#### Scenario: Disable an already disabled agent
- **WHEN** `POST /api/v1/agents/{id}/disable` is called on an already disabled agent
- **THEN** the agent is returned unchanged with `enabled: false`

#### Scenario: Disable non-existent agent
- **WHEN** `POST /api/v1/agents/{id}/disable` is called with a non-existent id
- **THEN** a 404 error response is returned

### Requirement: SpringBoot Toggle Proxy
Spring Boot SHALL proxy enable/disable requests to the Python AI Service.

#### Scenario: Proxy enable request
- **WHEN** `POST /api/agents/{id}/enable` is called
- **THEN** Spring Boot forwards to Python `POST /api/v1/agents/{id}/enable` and returns the result

#### Scenario: Proxy disable request
- **WHEN** `POST /api/agents/{id}/disable` is called
- **THEN** Spring Boot forwards to Python `POST /api/v1/agents/{id}/disable` and returns the result
```

