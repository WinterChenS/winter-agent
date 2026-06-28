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
