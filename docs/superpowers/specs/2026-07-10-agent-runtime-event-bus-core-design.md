---
comet_change: agent-runtime-event-bus-core
role: technical-design
canonical_spec: openspec
---

# Agent Runtime Event Bus Core Design

## Context

V0.8 要把 Agent Runtime 中分散的工具进度、图节点状态和后续 LLM 生命周期信号统一成内部事件流。当前代码已有 `ai_service/core/streaming_event_bus.py`，它是每次 chat stream 内部使用的 `asyncio.Queue` 旁路：生产者调用 `emit()`，FastAPI SSE runner 通过 `events()` 消费。这个模型很适合实时推送，但还不是通用 Event Bus：缺少标准事件模型、订阅生命周期、topic 匹配和可复用发布接口。

本设计只覆盖 `agent-runtime-event-bus-core`。它建立核心抽象和兼容边界，不接入 LLM/Tool/Graph 事件源，不实现 SSE 映射，也不做事件持久化。后续 changes 会基于这里的核心能力继续推进。

## Confirmed Direction

采用“核心可实例化 + 默认 request-scoped”。

`EventBus` 是普通可实例化对象，不是强制全局单例。Agent Runtime 默认在每个 chat request 内创建独立 bus，以避免跨请求事件泄漏。后续 `agent-runtime-event-store`、metrics 或 SSE adapter 可以作为订阅者挂到请求 bus 上；如果未来确实需要跨请求观测聚合，再通过桥接订阅者或替换实现扩展，而不是在 core 阶段引入全局 bus。

## Architecture

新增一个运行时事件模块，建议路径为 `ai_service/core/event_bus.py`，也可以按现有结构拆成 `ai_service/domain/runtime_event.py` 和 `ai_service/core/event_bus.py`。核心对象如下：

- `RuntimeEvent`
  - dataclass，字段为 `event_id`、`event_type`、`timestamp`、`source`、`trace_id`、`span_id`、`payload`、`metadata`。
  - 提供 `create()` helper，为 `event_id`、`timestamp`、`metadata` 填充默认值。
  - 提供 `to_dict()`，供 SSE adapter、store 和测试使用。

- `Subscription`
  - dataclass，字段为 `subscription_id`、`topic`、`handler`。
  - handler 接收 `RuntimeEvent`，可为 sync 或 async；实现时统一包装为 awaitable，降低调用方复杂度。

- `EventBus`
  - `subscribe(topic, handler) -> Subscription`
  - `unsubscribe(subscription_id) -> None`
  - `publish(event: RuntimeEvent) -> None`
  - 内部维护订阅表，不持有跨实例全局状态。

数据流：

```text
runtime component
  -> RuntimeEvent.create(...)
  -> request EventBus.publish(event)
  -> matching subscriptions
  -> SSE bridge / event store / metrics / tests
```

## Topic Matching

`event_type` 同时作为 topic。初版只支持两类匹配：

- 精确匹配：`tool.invoke` 只匹配 `tool.invoke`
- 单段 wildcard：`tool.*` 匹配 `tool.invoke`、`tool.result`，但不匹配 `tool.sandbox.output`

不实现 `**`、正则、前缀 glob 或复杂过滤表达式。这样足够覆盖 V0.8 路线图中的 `llm.*`、`tool.*`、`graph.*`，同时保持实现和测试清晰。

## Publish Semantics

`publish()` 是运行时观测路径，不是业务强一致路径。

- 没有订阅者时，`publish()` 正常完成。
- 某个 handler 抛异常时，Event Bus 记录日志并继续处理其他订阅者。
- handler 失败不向 LLM、Tool 或 Graph 主流程传播。
- Event Bus core 不负责 token 级背压策略；高频 token 是否进入 bus 由 event sources change 决定。

实现可以顺序 await 匹配 handler，也可以为 handler 创建任务。为了降低第一版复杂度，建议先顺序 await，并用 try/except 隔离 handler 失败。若后续性能需要，再引入并发分发或队列 worker。

## StreamingEventBus Compatibility

现有 `StreamingEventBus` 暂不删除。推荐第一步保持 API 兼容：

- 继续支持 `emit(event_type, **data)`
- 继续支持 `events()` async generator
- 继续支持 `close()`

实现策略有两种，优先使用低风险策略：

1. 保持 `StreamingEventBus` 现状，只新增核心 Event Bus，并用测试保证现有行为不退化。
2. 在后续 SSE adapter change 中，让 `StreamingEventBus` 包装 `EventBus`，把 `emit()` 转为 `RuntimeEvent`，把订阅输出转回旧 `StreamingEvent`。

本 change 的目标是建立核心能力和兼容边界，不强制一次性迁移所有 streaming 调用点。

## Testing Strategy

新增或扩展 AI service 单元测试：

- `RuntimeEvent`
  - 默认生成 `event_id`
  - 默认生成毫秒时间戳
  - 缺省 metadata 为 `{}`
  - `to_dict()` 字段完整

- `EventBus`
  - 精确 topic 订阅能收到匹配事件
  - `tool.*` 能收到单段匹配事件
  - wildcard 不匹配多段事件
  - unsubscribe 后不再收到事件
  - 无订阅者 publish 成功
  - 一个 handler 抛错不影响其他 handler 和发布方
  - 两个 EventBus 实例互相隔离，验证 request-scoped 语义

- `StreamingEventBus` compatibility
  - `emit()` 后 `events()` 能收到旧 `StreamingEvent`
  - `close()` 能结束 async generator
  - 现有 `test_parallel_protocol`、`test_code_sandbox` 不回退

## Spec Patch

已回写 OpenSpec delta spec：

- 明确 Event Bus MUST 是可实例化核心对象，而不是强制全局单例。
- 明确 Agent Runtime 默认 SHALL 为每个 chat request 创建独立 Event Bus 实例。
- 新增 request-scoped 事件隔离场景：两个请求使用独立 Event Bus 时，事件不会跨请求投递。

## Risks and Mitigations

- 单进程实现不支持跨 worker 广播  
  Mitigation：本 change 不承诺跨进程可靠投递；接口保持可替换，未来可接外部实现。

- request-scoped bus 不天然提供跨请求聚合  
  Mitigation：事件存储和 metrics 通过订阅者解决，不在 core 中引入全局默认。

- handler 慢或失败影响主流程  
  Mitigation：handler 异常被捕获；慢 handler 的超时/并发策略留作后续优化，第一版用测试锁定失败隔离。

- 与现有 `StreamingEventBus` 双轨并存造成混乱  
  Mitigation：本 change 只新增核心抽象和兼容测试；迁移由后续 SSE adapter change 完成。
