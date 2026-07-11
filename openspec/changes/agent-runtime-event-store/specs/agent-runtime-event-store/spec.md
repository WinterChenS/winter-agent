## ADDED Requirements

### Requirement: Optional Runtime Event Persistence
系统 SHALL 提供可选的 RuntimeEvent 持久化能力。

持久化实现 MUST 复用项目已有 PostgreSQL 连接配置，不得要求 Redis、RabbitMQ、Kafka 或新增数据库组件。

#### Scenario: Persist enabled event
- **WHEN** Event Store 已启用且收到 RuntimeEvent
- **THEN** 系统将事件写入 PostgreSQL

#### Scenario: Persistence disabled
- **WHEN** Event Store 被配置为关闭
- **THEN** RuntimeEvent 仍可实时发布和订阅，但不会写入数据库

### Requirement: Trace and Conversation Event Query
系统 SHALL 支持按 trace、conversation、事件类型和时间范围查询持久化事件。

#### Scenario: Query by trace ID
- **WHEN** 调用方使用 `trace_id` 查询事件
- **THEN** 系统返回该 trace 下按时间排序的事件列表

#### Scenario: Query by conversation ID
- **WHEN** 调用方使用 `conversation_id` 查询事件
- **THEN** 系统返回该会话相关的事件列表

### Requirement: Persistence Failure Isolation
系统 SHALL 隔离持久化失败与 Agent 主执行流程。

数据库写入失败 MUST 不导致 LLM、工具或图节点主流程失败。

#### Scenario: Database write fails
- **WHEN** Event Store 写入 PostgreSQL 失败
- **THEN** 系统记录错误并继续运行时主流程

#### Scenario: Query storage unavailable
- **WHEN** 查询事件时数据库不可用
- **THEN** API 返回明确错误，而不是影响实时聊天流
