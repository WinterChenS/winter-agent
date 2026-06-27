# Brainstorm Summary

- Change: ai-chat-layer-rewrite
- Date: 2026-06-26

## 确认的技术方案

### Zustand Store — Map-based Shape
- `messages: Record<string, Message>`（keyed by messageId），O(1) 局部更新
- `messageOrder: string[]` 维护顺序，组件选择器按 `messageOrder.map(id => messages[id])` 获取
- Actions: addMessage, appendDelta, appendReasoning, upsertToolCall, completeMessage, setAgentId, setConversationId

### messageId 生成策略
- 前端生成 UUID v4，在用户发送消息时创建
- 消息气泡在点击发送瞬间渲染（status: "streaming"），无需等待首个 SSE 事件
- messageId 作为 DB 主键和 SSE 事件关联键

### ToolCall ID 策略
- Python 端为每次工具调用生成独立 `toolCallId`
- 前端 `upsertToolCall(messageId, toolCall)` 按 `toolCall.id` 做 Map 合并
- 同一 Agent 多次调用同名工具时不冲突

### 流式更新性能优化
- `requestAnimationFrame` 合并批处理：多个 delta 事件合并到一帧内
- 最多 60fps 渲染，CPU 友好，无闪烁
- reasoning delta 同理合并

### 旧代码迁移策略
- 路由级 Feature Flag：`/chat/:id` 保留旧 UI，`/chat-v2/:id` 使用新 ChatContainer
- 开发验证完成后切换路由，旧文件保留加 `@deprecated` 标注
- 回滚成本 = 一行路由

### 测试策略
- Python: pytest 单元测试 event_envelope + 集成测试 SSE 流事件序列
- Spring Boot: WebTestClient 集成测试 Agent CRUD + SSE 透传
- 前端: vitest 单元测试 chatStore actions + vitest + testing-library 组件测试
- E2E: Playwright 全链路测试
- 更新 `scripts/test_chat_scenarios.py`（不新建文件）适配新协议

## 关键取舍与风险

- **[取舍]** 一次性协议切换，不做兼容过渡 → 同一 branch 内三层同步升级
- **[风险]** Shiki 包体积大 → @shikijs/core + 按需加载语言，非首屏路径 lazy import
- **[风险]** 消息持久化增加 AI Service 延迟 → 异步写入，不阻塞 SSE 流

## 测试策略

1. Python: 新 event_envelope 函数输出格式验证 + chat.py SSE 事件序列集成测试
2. Spring Boot: AgentController + ChatController WebTestClient 集成测试
3. 前端: chatStore vitest 单元测试 + 关键组件 (MessageBubble/ReasoningPanel/ToolCallPanel) testing-library 测试
4. E2E: Playwright 全链路 Agent 选择 → 流式对话 → 历史加载

## Spec Patch

无（现有 delta specs 已覆盖确认的设计决策）
