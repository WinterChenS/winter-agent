# Comet Design Handoff

- Change: agent-runtime-event-bus-core
- Phase: design
- Mode: compact
- Context hash: 1d80f21d3c53ba1d941b21012acc3cefecdf9ad2001ae1b0ca3628022a8f2491

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/agent-runtime-event-bus-core/proposal.md

- Source: openspec/changes/agent-runtime-event-bus-core/proposal.md
- Lines: 1-28
- SHA256: d217d84537818b73c7aa9ef034b01890d2f176706ab2e6fdf8929a4346e2d4c8

```md
## Why

V0.8 需要把 Agent Runtime 中分散的工具进度、图执行状态和后续 LLM 生命周期信号统一成运行时事件流。当前代码已经有 `StreamingEventBus` 雏形，但它只服务于单次 SSE 旁路，缺少标准事件模型、订阅语义和可复用的发布接口。

## What Changes

- 引入进程内 Runtime Event Bus 核心，不新增 Redis、RabbitMQ、Kafka 等外部依赖组件。
- 定义标准 `RuntimeEvent` 数据结构，包含事件 ID、类型、时间戳、来源、trace/span、payload 和 metadata。
- 提供发布、订阅、取消订阅接口，支持 topic 精确匹配和 wildcard 匹配。
- 保留异步非阻塞发布语义，避免事件处理阻塞 Agent 主执行路径。
- 为后续 LLM/Tool/Graph 事件源、SSE 适配和可选持久化提供稳定契约。

## Capabilities

### New Capabilities

- `agent-runtime-event-bus`: Agent Runtime 的进程内事件总线、标准事件模型、发布订阅和 wildcard 路由能力。

### Modified Capabilities

- 无。

## Impact

- 主要影响 `ai_service/core`、`ai_service/domain` 或新增 runtime event 模块。
- 现有 `StreamingEventBus` 需要被兼容包裹、迁移或作为新总线的轻量适配层。
- 不影响前端、Spring BFF、Docker Compose 外部组件拓扑。
- 后续 changes 将依赖该核心能力接入事件源、SSE 和持久化。
```

## openspec/changes/agent-runtime-event-bus-core/design.md

- Source: openspec/changes/agent-runtime-event-bus-core/design.md
- Lines: 1-61
- SHA256: f4177a87df760cde0d0a513096c3de4294bdf61f6e0b8a580ffe0a9850035898

```md
## Context

V0.8 的目标是建立 Agent Runtime 全事件流。当前 `ai_service/core/streaming_event_bus.py` 已有基于 `asyncio.Queue` 的 `StreamingEventBus`，主要用于单次 chat stream 内部把工具进度推给 SSE；它不是通用发布订阅总线，也没有标准事件模型、topic 路由或订阅生命周期。

本 change 是后续事件源、SSE 适配和事件存储的基础层。设计约束是本版本不引入 Redis、RabbitMQ、Kafka 等外部依赖组件，优先保持本地开发、Docker Compose 和现有部署拓扑简单。

## Goals / Non-Goals

**Goals:**
- 定义标准 `RuntimeEvent` 模型，成为内部事件流的统一契约。
- 提供进程内 Event Bus，支持发布、订阅、取消订阅和 wildcard topic。
- 保持发布路径非阻塞或可控降级，避免影响 Agent 主流程。
- 为现有 `StreamingEventBus` 提供迁移/兼容路径。

**Non-Goals:**
- 不引入外部 MQ 或分布式事件总线。
- 不实现事件持久化、回放或查询 API。
- 不接入 LLM/Tool/Graph 事件源。
- 不改变前端 SSE 协议。

## Decisions

1. 使用进程内异步 Event Bus 作为 V0.8 默认实现。

   原因：当前系统主要运行在 FastAPI 进程内，已有 `asyncio` 事件循环和 `StreamingEventBus` 经验。相比 Redis/RabbitMQ，进程内实现更符合“不新增外部组件”的约束，也能先稳定内部事件契约。

   替代方案：Redis/RabbitMQ 可提供跨进程可靠投递，但会增加部署和运维成本，放到未来扩展。

2. `RuntimeEvent.event_type` 同时作为 topic。

   原因：路线图中的 `llm.request`、`tool.result`、`graph.enter` 天然是 topic 层级。这样可以用 `tool.*` 订阅一类事件，避免额外维护 topic 字段。

   替代方案：独立 `topic` 字段会更灵活，但容易与 `event_type` 分叉，增加协议复杂度。

3. 订阅处理器失败不向发布方传播。

   原因：事件总线是观测和协作基础设施，不应让审计、指标或 SSE 消费方故障破坏 LLM/Tool 主链路。

   替代方案：强一致事件投递会提升可靠性，但不适合当前 runtime 主路径。

4. 保留 `StreamingEventBus` 兼容层。

   原因：现有 chat stream 已依赖 `events()` 异步生成器。核心总线落地时可以提供桥接订阅，把 RuntimeEvent 转为旧的 streaming side channel，降低一次性迁移风险。

## Risks / Trade-offs

- [Risk] 单进程 Event Bus 不支持跨 worker 广播 -> [Mitigation] 在 design 和接口中保留实现替换边界，V0.8 不承诺跨进程可靠投递。
- [Risk] wildcard 匹配实现过度复杂 -> [Mitigation] 仅支持单段 `*`，例如 `tool.*`，不实现多段 glob。
- [Risk] 高吞吐 token 事件造成队列积压 -> [Mitigation] 核心层提供队列/处理错误保护，token 事件策略由事件源 change 决定。

## Migration Plan

1. 新增 runtime event 模型和 Event Bus 模块。
2. 为 `StreamingEventBus` 提供桥接或兼容包装。
3. 添加单元测试覆盖发布、订阅、取消订阅、wildcard 和处理器失败。
4. 后续 changes 再逐步接入事件源和 SSE。

## Open Questions

- 是否需要为每个请求创建独立 Event Bus，还是使用应用级 bus 加 request scope 过滤？
- 订阅处理器是否需要超时配置，默认超时是多少？
```

## openspec/changes/agent-runtime-event-bus-core/tasks.md

- Source: openspec/changes/agent-runtime-event-bus-core/tasks.md
- Lines: 1-23
- SHA256: c83fdcdbfcb8bbbd9ec7cdfdf0e22f1864a1ef46d1049553ffe0b23fdfe0653f

```md
## 1. Event Model

- [ ] 1.1 Add a `RuntimeEvent` model with event ID, event type, timestamp, source, trace/span IDs, payload, and metadata.
- [ ] 1.2 Add helpers for creating events with default timestamp, generated ID, and empty metadata.
- [ ] 1.3 Add unit tests for required fields, default values, and serialization.

## 2. Event Bus Core

- [ ] 2.1 Implement in-process Event Bus publish, subscribe, and unsubscribe APIs.
- [ ] 2.2 Implement exact topic matching and single-segment wildcard matching.
- [ ] 2.3 Ensure subscriber failures are isolated from publish callers.
- [ ] 2.4 Add tests for exact subscriptions, wildcard subscriptions, no-subscriber publish, unsubscribe, and handler failure.

## 3. Compatibility and Integration Boundary

- [ ] 3.1 Add a compatibility path or adapter for existing `StreamingEventBus` usage.
- [ ] 3.2 Document the no-external-component constraint in code comments or module docs where the bus implementation is introduced.
- [ ] 3.3 Verify existing tests for streaming event behavior still pass.

## 4. Validation

- [ ] 4.1 Run targeted AI service tests for event bus and streaming compatibility.
- [ ] 4.2 Run OpenSpec validation for `agent-runtime-event-bus-core`.
```

## openspec/changes/agent-runtime-event-bus-core/specs/agent-runtime-event-bus/spec.md

- Source: openspec/changes/agent-runtime-event-bus-core/specs/agent-runtime-event-bus/spec.md
- Lines: 1-57
- SHA256: 21db251523c179515a1bebfa5d51c3ac84f071de6446f549b25cc646c77a38e7

```md
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
```

