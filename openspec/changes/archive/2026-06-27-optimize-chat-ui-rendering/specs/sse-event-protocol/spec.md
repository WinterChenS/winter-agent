## MODIFIED Requirements

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
