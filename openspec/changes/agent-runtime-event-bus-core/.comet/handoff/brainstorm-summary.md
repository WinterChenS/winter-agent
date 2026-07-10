# Brainstorm Summary

- Change: agent-runtime-event-bus-core
- Date: 2026-07-10

## 确认的技术方案

- V0.8 Event Bus Core 不引入 Redis、RabbitMQ、Kafka 等外部消息组件。
- OpenSpec canonical spec 要求 `RuntimeEvent` 至少包含 `event_id`、`event_type`、`timestamp`、`source`、`trace_id`、`span_id`、`payload`、`metadata`。
- Event Bus 需要支持 publish、subscribe、unsubscribe、精确 topic、单段 wildcard topic、无订阅者发布成功、订阅处理失败隔离。
- 当前 `StreamingEventBus` 是基于 `asyncio.Queue` 的单请求 SSE 旁路，`chat.py` 消费 `events()`，工具和图节点通过 `emit()` 推送旧事件。
- 采用“核心可实例化 + 默认 request-scoped”。`EventBus` 是普通可实例化对象，不持有强制全局单例状态；chat runtime 默认每个请求创建独立 bus，后续 store/metrics 可以通过订阅者或桥接器挂到请求 bus。

## 关键取舍与风险

- 取舍：默认 request-scoped 提供最强请求隔离，但不天然提供跨请求观测聚合；后续 `agent-runtime-event-store` 和 metrics 订阅者负责跨请求查询/聚合。
- 风险：全局 bus 会带来跨请求事件泄漏和订阅清理复杂度，因此本 change 不采用全局默认。
- 风险：高吞吐 token 事件可能造成队列积压；本 change 只提供核心发布订阅能力，token 策略留给事件源 change。
- 风险：handler 执行过慢可能拖累 publish；实现时需要隔离 handler 异常，并在测试中覆盖失败不传播。

## 测试策略

- `RuntimeEvent` 默认字段、空 metadata、序列化。
- `EventBus` 精确 topic、`tool.*` wildcard、unsubscribe、无订阅者 publish。
- handler 抛错不影响其他订阅者和发布方。
- 兼容测试覆盖现有 `StreamingEventBus.emit/events/close` 行为不退化。

## Spec Patch

- 回写 delta spec：补充核心 `EventBus` 可实例化且默认 request-scoped 的要求与场景。
- 回写 delta spec：补充同一请求内事件隔离、不同请求之间不互相投递的验收场景。
