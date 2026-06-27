# sse-event-protocol Specification

## Purpose
TBD - created by archiving change ai-chat-layer-rewrite. Update Purpose after archive.
## Requirements
### Requirement: message.delta Event
系统 SHALL 使用 `message.delta` 事件传输 token 级别的文本增量。

事件格式：
```json
{
  "type": "message.delta",
  "messageId": "uuid",
  "agentId": "agent-001",
  "delta": "文本增量"
}
```

#### Scenario: Token-level streaming
- **WHEN** AI 生成回复文本
- **THEN** 每个 token 通过 `message.delta` 事件发送，前端增量渲染

#### Scenario: Multi-message delta routing
- **WHEN** 流式响应包含多个工具调用结果
- **THEN** 每个 `message.delta` 事件携带 `messageId` 标识归属

### Requirement: message.tool_call Event
系统 SHALL 使用 `message.tool_call` 事件传输工具调用状态。

事件格式：
```json
{
  "type": "message.tool_call",
  "messageId": "uuid",
  "agentId": "agent-001",
  "toolCall": {
    "name": "search",
    "arguments": { "query": "..." },
    "status": "running" | "done" | "failed",
    "result": "..."
  }
}
```

#### Scenario: Tool execution lifecycle via SSE
- **WHEN** AI 调用工具
- **THEN** 前端收到 `message.tool_call` 事件（status: "running"），执行完成后收到同一 toolCall 的更新事件（status: "done"）

#### Scenario: Tool call failure
- **WHEN** 工具执行失败
- **THEN** `message.tool_call` 事件 status 为 "failed"，result 包含错误信息

### Requirement: message.reasoning Event
系统 SHALL 使用 `message.reasoning` 事件传输 AI 思考过程。

事件格式：
```json
{
  "type": "message.reasoning",
  "messageId": "uuid",
  "agentId": "agent-001",
  "delta": "思考内容增量"
}
```

#### Scenario: Streaming reasoning display
- **WHEN** AI 在生成回复前进行思考
- **THEN** 前端通过 `message.reasoning` 事件收到增量思考内容，在 ReasoningPanel 中折叠展示

### Requirement: message.done Event
系统 SHALL 使用 `message.done` 事件标识消息流结束。

事件格式：
```json
{
  "type": "message.done",
  "messageId": "uuid",
  "status": "done" | "error",
  "error": "可选错误信息"
}
```

#### Scenario: Successful stream completion
- **WHEN** AI 完成完整回复
- **THEN** 前端收到 `message.done`（status: "done"），将消息状态更新为 "done"

#### Scenario: Stream error
- **WHEN** 流式传输中断
- **THEN** 前端收到 `message.done`（status: "error"），将消息状态更新为 "error" 并显示错误信息

### Requirement: Event Envelope Standardization
所有 SSE 事件 SHALL 使用 `EventEnvelope` 包装格式：业务字段嵌套在 `payload` 对象中，顶层仅包含元数据字段（`type`、`schemaVersion`、`conversationId`、`turnId`、`agentId`、`traceId`、`spanId`、`timestamp`）。前端 SHALL 从 `payload` 中提取事件特定的业务字段。

事件通用格式：
```json
{
  "type": "message.delta",
  "schemaVersion": "1.0",
  "conversationId": "uuid",
  "turnId": "uuid",
  "agentId": "agent-001",
  "traceId": "uuid",
  "spanId": "uuid",
  "timestamp": 1234567890000,
  "payload": {
    "messageId": "uuid",
    "delta": "文本增量"
  }
}
```

#### Scenario: Event metadata availability
- **WHEN** 前端收到任意 SSE 事件
- **THEN** 事件包含顶层元数据：`type`、`schemaVersion`、`conversationId`、`agentId`、`timestamp`
- **AND** 业务字段（`messageId`、`delta`、`toolCall` 等）从 `payload` 对象中提取

#### Scenario: Flat event backward compatibility
- **WHEN** 前端收到旧格式事件（业务字段在顶层，无 payload 包装）
- **THEN** 系统兼容处理：优先从 `event.payload` 读取，fallback 到 `event` 顶层读取

