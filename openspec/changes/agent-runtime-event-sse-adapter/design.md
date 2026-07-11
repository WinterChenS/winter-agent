## Context

前端聊天 UI 已消费 SSE envelope，包括 `message.delta`、`message.tool_call`、`message.done`、工具进度和图片事件。RuntimeEvent 引入后，不能把内部事件结构直接暴露给前端，否则会让 UI 耦合 runtime 实现细节。当前 `api/events/event_mapper.py` 和 `api/routes/chat.py` 已承担一部分映射和合并职责，本 change 将其收敛为明确适配层。

本 change 依赖 Event Bus core，通常也会受 event sources 输出影响。它不负责创建事件源或持久化事件。

## Goals / Non-Goals

**Goals:**
- 将 RuntimeEvent 映射为 SSE EventEnvelope。
- 保持现有前端聊天事件兼容。
- 统一 chat stream 中 Graph 事件、Event Bus 事件、完成和错误事件的合并。
- 为新 runtime 事件提供透传或过滤策略。

**Non-Goals:**
- 不重做前端聊天 UI。
- 不修改 Spring BFF 的 SSE 代理模型。
- 不持久化事件。
- 不要求前端理解所有 RuntimeEvent 内部字段。

## Decisions

1. 适配层输出 EventEnvelope，而不是裸 RuntimeEvent。

   原因：现有 `sse-event-protocol` 已规范 envelope 元数据和 payload。继续使用 envelope 可以保持前端兼容和 trace 字段一致。

   替代方案：直接把 RuntimeEvent 作为 SSE data。这样实现简单，但会破坏前端协议边界。

2. 对 UI 已依赖事件做兼容映射。

   原因：例如工具生命周期 runtime 事件可以映射到现有工具面板能理解的状态事件。这样 V0.8 不需要先改造 UI。

   替代方案：要求前端处理 `tool.invoke/tool.result`。这会扩大本 change 范围。

3. chat stream 继续由 FastAPI 合并多个异步来源。

   原因：当前 `chat.py` 已有 graph runner + bus runner + queue merge 模式。适配后可保留这个可靠路径，只把 bus event 类型从旧 `StreamingEvent` 演进到 `RuntimeEvent`。

   替代方案：完全依赖 LangGraph `astream_events`。这不能覆盖工具内部进度和未来 store/audit 订阅。

4. 未识别 runtime 事件默认作为观测事件透传或过滤。

   原因：不是所有 runtime 事件都应驱动聊天 UI。适配层需要明确策略，避免前端收到噪声。

## Risks / Trade-offs

- [Risk] 双格式兼容导致 mapper 复杂 -> [Mitigation] 将兼容逻辑集中在 adapter 测试覆盖，业务组件只读 envelope。
- [Risk] 事件顺序在 graph/bus 合并时轻微交错 -> [Mitigation] 保证单请求内可读顺序和最终 completion，不承诺严格全局排序。
- [Risk] 新事件类型前端未知 -> [Mitigation] 未识别事件不破坏消息状态，必要时过滤。

## Migration Plan

1. 新增 RuntimeEvent 到 SSE envelope mapper。
2. 将旧 `StreamingEvent` mapper 迁移或包裹到新 mapper。
3. 更新 chat stream merge 逻辑使用适配层。
4. 添加 SSE mapper 测试和 chat stream smoke 测试。

## Open Questions

- 未识别 runtime 事件是否应默认发送给前端调试面板，还是默认只记录日志？
- 工具事件最终是否统一映射为 `message.tool_call`，还是保留 `tool.started/tool.finished` 双轨兼容？
