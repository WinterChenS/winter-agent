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
