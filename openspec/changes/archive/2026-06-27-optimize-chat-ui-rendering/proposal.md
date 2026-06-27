## Why

当前 AI Chat 前端存在 4 个影响用户体验的问题：页面刷新后历史消息丢失或显示不一致、中文输入法回车误触发发送、tool 调用 UI 散乱且无流式状态反馈、session 切换时数据偶有错乱。这些问题导致用户感知的前端质量远低于 ChatGPT/Claude Code 水平，需要在不动后端架构的前提下集中修复。

## What Changes

- **修复 SSE 事件解析**：前端适配后端 EventEnvelope 的 payload 包装格式，确保 `message.delta`、`message.tool_call`、`message.reasoning` 等事件正确解析
- **添加 IME 组合输入守卫**：InputBox 增加 `compositionstart`/`compositionend` 事件处理，防止中文输入法回车误触发发送
- **Tool 调用聚合展示**：同一轮对话的多个 tool call 合并为统一的 ToolExecutionPanel，支持折叠/展开和状态流转（pending → running → success/failed）
- **Session 数据稳定回显**：基于 route sessionId 做唯一数据源，loadHistory 支持完整的 message + toolCalls + images 字段恢复
- **历史消息完整恢复**：页面刷新后通过 re-fetch history API 完整重建 UI 状态，包括消息、tool 调用记录、执行顺序

## Capabilities

### New Capabilities
- `chat-history-restore`: 页面刷新后通过 history API 完整恢复会话 UI，包括 message + toolCalls + 顺序
- `ime-input-guard`: 中文输入法 composition 事件处理，防止 IME 回车误触发消息发送

### Modified Capabilities
- `ai-chat-ui`: ToolCallPanel 改为聚合展示（同一轮 tool calls 合并 + 折叠/展开）；MessageList 增加 session hydration 支持；InputBox 增加 IME 状态锁
- `sse-event-protocol`: 前端事件解析适配后端 EventEnvelope payload 包装格式（`event.payload.*` 替代 `event.*` 直读）

## Impact

- 仅修改 `frontend/src/features/ai-chat/` 下的组件、store、services、hooks
- 可能更新 `frontend/src/types/chat.ts` 类型定义（增加 `ToolCall.id` 等字段对齐后端）
- 不修改任何后端代码（Python/Java）
- 不改变现有 API 端点路径和 SSE 协议
