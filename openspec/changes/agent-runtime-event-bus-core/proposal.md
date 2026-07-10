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
