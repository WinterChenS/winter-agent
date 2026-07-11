## Why

实时事件流解决了在线观察问题，但排查 Agent 执行链路仍需要按 trace 或 conversation 查询历史事件。V0.8 的持久化应复用项目已有 PostgreSQL，而不是引入新的外部事件存储组件。

## What Changes

- 新增可选 Event Store，复用 PostgreSQL 持久化 RuntimeEvent。
- 支持按 `trace_id`、`conversation_id`、事件类型和时间范围查询事件链路。
- 提供开关或降级策略，确保持久化失败不阻塞 Agent 主流程。
- 保留未来替换为外部事件平台的接口边界，但本 change 不引入外部 MQ 或数据库。
- 不提供复杂回放 UI；先提供服务层和 API/测试可验证能力。

## Capabilities

### New Capabilities

- `agent-runtime-event-store`: RuntimeEvent 的可选 PostgreSQL 持久化、查询和降级能力。

### Modified Capabilities

- 无。

## Impact

- 主要影响 `ai_service/db`、`ai_service/core`、事件模型和 FastAPI 查询接口。
- 复用现有 `POSTGRES_URI`、连接池和迁移/初始化模式。
- 不修改 Docker Compose 的外部服务列表，不增加 Redis、RabbitMQ、Kafka 或新数据库。
