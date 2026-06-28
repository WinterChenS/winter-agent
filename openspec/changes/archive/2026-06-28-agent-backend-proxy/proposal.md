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
