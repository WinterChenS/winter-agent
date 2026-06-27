## ADDED Requirements

### Requirement: Session History Restore on Refresh
系统 SHALL 在页面刷新或首次加载时，通过 `GET /api/v1/history/{conversationId}` API 完整恢复会话历史，包括所有消息、tool 调用记录、执行顺序和关联图片。

#### Scenario: Full history restore after refresh
- **WHEN** 用户刷新 `/chat/:id` 页面
- **THEN** 系统调用 history API 获取该 conversation 的所有消息
- **AND** 每条消息包含完整的 content、reasoning、toolCalls、images 字段
- **AND** 消息按 createdAt 顺序渲染
- **AND** toolCalls 状态为最终状态（done/failed），不再显示 running 动画

#### Scenario: Tool calls restored from history
- **WHEN** history API 返回的消息包含 toolCalls 数组
- **THEN** 每条 tool call 的 name、status、result 完整恢复显示
- **AND** tool 调用按原始执行顺序展示

#### Scenario: Empty conversation restore
- **WHEN** 用户进入一个新的 conversation（无历史消息）
- **THEN** 页面显示空状态提示"开始新的对话"
- **AND** 不发起 history API 请求

### Requirement: History API Response Mapping
系统 SHALL 将 history API 返回的数据库记录正确映射为前端 Message 类型，包括字段类型转换和缺失字段默认值处理。

#### Scenario: Map database message to frontend Message
- **WHEN** history API 返回 `{ "messages": [{ "id": "...", "role": "assistant", "content": "...", "toolCalls": "[...]", ... }] }`
- **THEN** `toolCalls` 字段从 JSON string 解析为 `ToolCall[]`
- **AND** `createdAt` 从毫秒时间戳转换为前端可用的数值
- **AND** 缺失的 `status` 字段默认设为 `"done"`
- **AND** 缺失的 `images` 字段默认设为 `{}`

#### Scenario: Malformed toolCalls handling
- **WHEN** history API 返回的 `toolCalls` 字段为空字符串或 `null`
- **THEN** 系统将其处理为空数组 `[]`，不抛出异常
