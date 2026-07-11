## Context

Event Bus 核心完成后，需要从 LLM、Tool 和 Graph 节点产生标准 RuntimeEvent。当前系统的事件来源分散：LangGraph 的 `astream_events` 会被映射为 SSE，`execution_node` 可以接收 `event_bus` 推工具事件，部分工具支持 `execute_stream` 发进度。V0.8 要把这些分散信号统一为 runtime event source。

本 change 依赖 `agent-runtime-event-bus-core`。它不负责 SSE 映射和持久化，只负责在正确边界发布标准事件。

## Goals / Non-Goals

**Goals:**
- 在 LLM 调用开始、成功、失败时发布生命周期事件。
- 在工具调用开始、进度、成功、失败时发布生命周期事件。
- 在 LangGraph 节点进入、退出、异常时发布生命周期事件。
- 保证事件发布失败不改变原业务结果。

**Non-Goals:**
- 不实现 Event Bus 核心。
- 不定义前端展示方式或 SSE envelope 映射。
- 不做事件持久化。
- 不引入外部消息组件。

## Decisions

1. 在调用边界包装发布事件，而不是侵入第三方库内部。

   原因：LangChain、LangGraph 的内部事件形态会变化；在项目自己的 `_build_llm`、节点函数、工具 registry/execution 边界发布事件更稳定。

   替代方案：完全依赖 LangGraph `astream_events`。它适合流式输出，但难以覆盖工具自定义进度和统一错误语义。

2. Tool 事件优先接入 `ToolRegistry.invoke` 和 plan-execute 的单工具执行路径。

   原因：这两个位置覆盖工具生命周期的主要入口。工具内部进度仍通过 `execute_stream` 或工具显式 publisher 发 `tool.progress`。

   替代方案：要求每个工具自行发完整生命周期事件。这样会产生重复实现和不一致字段。

3. LLM token 事件先谨慎处理。

   原因：系统已有 `message.delta` 流式输出。逐 token 复制为 `llm.token` 可能造成事件风暴。默认先保证 `llm.request/response/error`，token 事件可通过采样、开关或映射复用处理。

   替代方案：所有 token 都发 RuntimeEvent。可观测性更强，但性能和前端噪声风险更高。

4. Graph 事件围绕业务节点发布。

   原因：当前 plan-execute-compose 主要节点是 `planning`、`execution`、`composer`。围绕这些节点发布 `graph.enter/exit/error`，比暴露 LangGraph 内部细粒度事件更稳定。

## Risks / Trade-offs

- [Risk] LLM 包装点遗漏某些调用路径 -> [Mitigation] 先覆盖 plan-execute-compose 主路径，并用测试锁定。
- [Risk] 工具执行路径存在并行和流式变体 -> [Mitigation] 在 registry 与 execution node 两层明确职责，避免重复发最终事件。
- [Risk] 事件字段泄漏敏感 prompt 或工具输入 -> [Mitigation] payload 只放必要摘要，敏感内容由发布点裁剪。

## Migration Plan

1. 在 runtime 上下文中传递 EventPublisher。
2. 接入 LLM request/response/error。
3. 接入 tool invoke/progress/result/error。
4. 接入 graph enter/exit/error。
5. 添加单元测试和主路径集成测试，确认主业务结果不受事件失败影响。

## Open Questions

- `llm.request` 是否记录完整 prompt、摘要还是 token 统计？
- 并行工具执行中同一工具多次调用的 `tool_call_id` 生成规则是否需要统一到核心层？
