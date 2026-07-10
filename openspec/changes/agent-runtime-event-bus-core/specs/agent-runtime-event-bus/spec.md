## ADDED Requirements

### Requirement: Runtime Event Model
系统 SHALL 定义标准 `RuntimeEvent` 模型，用于表示 Agent Runtime 内部事件。

`RuntimeEvent` MUST 至少包含 `event_id`、`event_type`、`timestamp`、`source`、`trace_id`、`span_id`、`payload` 和 `metadata` 字段。

#### Scenario: Create standard runtime event
- **WHEN** 运行时组件发布事件
- **THEN** 事件包含稳定的 ID、类型、时间戳、来源、追踪字段、业务负载和扩展元数据

#### Scenario: Missing optional metadata
- **WHEN** 发布方没有额外 metadata
- **THEN** 系统使用空对象表示 metadata，而不是省略字段或使用 null

### Requirement: In-process Event Bus
系统 SHALL 提供进程内 Event Bus，用于异步发布和订阅 `RuntimeEvent`。

Event Bus MUST 不依赖 Redis、RabbitMQ、Kafka 或任何新增外部消息组件。

Event Bus MUST 是可实例化核心对象，而不是强制全局单例。Agent Runtime 默认 SHALL 为每个 chat request 创建独立 Event Bus 实例，以隔离不同请求的事件流。

#### Scenario: Publish event to subscriber
- **WHEN** 发布方发布匹配订阅 topic 的事件
- **THEN** 订阅方收到该事件

#### Scenario: Publish without subscribers
- **WHEN** 发布方发布没有任何订阅者匹配的事件
- **THEN** 发布操作成功完成且不影响主执行流程

#### Scenario: Request-scoped event isolation
- **WHEN** 两个 chat request 分别使用独立 Event Bus 实例
- **THEN** 发布到第一个请求 Event Bus 的事件不会投递给第二个请求的订阅者

### Requirement: Topic Subscription and Wildcard Matching
系统 SHALL 支持按 topic 订阅事件，并支持 `*` 通配符匹配单段事件类型。

#### Scenario: Exact topic subscription
- **WHEN** 订阅方订阅 `tool.invoke`
- **THEN** 仅 `tool.invoke` 事件会触发该订阅方

#### Scenario: Wildcard topic subscription
- **WHEN** 订阅方订阅 `tool.*`
- **THEN** `tool.invoke`、`tool.progress`、`tool.result` 和 `tool.error` 等单段匹配事件会触发该订阅方

### Requirement: Non-blocking Publish Semantics
系统 SHALL 让事件发布对 Agent 主执行路径保持非阻塞或可控降级。

订阅处理失败 MUST 不导致 LLM、工具或图节点主流程失败。

#### Scenario: Subscriber handler fails
- **WHEN** 某个订阅处理器抛出异常
- **THEN** Event Bus 记录该错误并继续处理主流程

#### Scenario: Slow subscriber
- **WHEN** 某个订阅处理器执行较慢
- **THEN** 系统不会无限期阻塞事件发布方
