## Why

现有聊天 UI 已依赖 SSE envelope 展示 token、工具进度、图片和完成事件。V0.8 引入 RuntimeEvent 后，需要一个兼容适配层把内部事件流稳定映射到前端协议，而不是让前端直接耦合运行时内部事件结构。

## What Changes

- 新增 RuntimeEvent 到 SSE envelope 的映射适配器。
- 兼容现有 `message.delta`、`message.tool_call`、`tool.started/tool.finished`、`image.uploaded` 等前端已消费事件。
- 对新增 runtime 事件提供透传或规范化策略，避免破坏现有聊天流。
- 在 FastAPI chat stream 中统一合并 LangGraph 事件、Event Bus 事件和完成/错误事件。
- 不重做前端 UI，只做必要的事件兼容和测试覆盖。

## Capabilities

### New Capabilities

- `agent-runtime-event-sse-adapter`: RuntimeEvent 到 SSE envelope 的实时适配、兼容映射和流式合并能力。

### Modified Capabilities

- `sse-event-protocol`: 扩展 SSE 协议以承载 RuntimeEvent 映射结果，同时保持现有前端事件兼容。

## Impact

- 主要影响 `ai_service/api/events/event_mapper.py`、`ai_service/api/routes/chat.py` 和相关 SSE 协议测试。
- 前端 `frontend/src/features/ai-chat` 只在必要时更新类型和兼容处理。
- Spring BFF 继续透传 SSE，不引入新的后端协议层。
