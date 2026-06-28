## 1. DB Migration

- [x] 1.1 Create `V003__agent_upgrade.sql` with 9 new columns (icon, agent_type, avatar_url, is_builtin, tags, metadata, created_by, updated_by, version)
- [x] 1.2 Add backfill SQL for existing seed agents (is_builtin = true)

## 2. Python Agent Model & Repository Enhancement

- [x] 2.1 Extend `AgentDefinition` Pydantic model with new fields (icon, agent_type, avatar_url, is_builtin, tags, metadata, created_by, updated_by, version)
- [x] 2.2 Add `set_enabled(agent_id, enabled)` method to `AgentRepository` base and `PostgresAgentRepository`
- [x] 2.3 Add `clone(agent_id)` method to `AgentRepository` base and `PostgresAgentRepository`
- [x] 2.4 Update `_row_to_agent()` and `create()`/`update()` to handle new fields

## 3. Python Agent API Endpoints

- [x] 3.1 Add `POST /api/v1/agents/{id}/enable` endpoint
- [x] 3.2 Add `POST /api/v1/agents/{id}/disable` endpoint
- [x] 3.3 Add `POST /api/v1/agents/{id}/clone` endpoint (display_name append " (Copy)", name append "-copy")

## 4. SpringBoot DTOs

- [x] 4.1 Create `AgentRequest` record (input DTO with validation annotations)
- [x] 4.2 Create `AgentResponse` record (output DTO mapping all agent fields)

## 5. SpringBoot AgentClient

- [x] 5.1 Create `AgentClient` component with WebClient methods: listAll, getById, create, update, delete, enable, disable, clone
- [x] 5.2 Configure base URL from `aichat.ai-service-url` property

## 6. SpringBoot AgentService

- [x] 6.1 Create `AgentService` with business logic: CRUD delegation, enable/disable, clone
- [x] 6.2 Add logging for each operation
- [x] 6.3 Add exception handling (connection errors → 503, 4xx/5xx propagation)

## 7. SpringBoot AgentController

- [x] 7.1 Rewrite `AgentController` with full endpoints: GET list/detail, POST create, PUT update, DELETE delete, POST enable, POST disable, POST clone
- [x] 7.2 Wire endpoints through `SecurityConfig` (require JWT authentication)

## 8. Verification

- [x] 8.1 Verify migration applies cleanly and existing seed data is preserved
- [x] 8.2 Verify Python enable/disable/clone endpoints via curl/HTTP test
- [x] 8.3 Verify SpringBoot proxy endpoints return correct data
- [x] 8.4 Verify existing chat SSE flow is unaffected (send a chat message)
