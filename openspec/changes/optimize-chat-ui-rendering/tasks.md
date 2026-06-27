## 1. SSE 事件解析修复

- [x] 1.1 修复 `chatApi.ts` 的 `handleEvent` 函数：从 `event.payload` 中提取 `messageId`、`delta`、`toolCall` 等业务字段，兼容 flat 格式 fallback
- [x] 1.2 修复 `chatApi.ts` 的 `agent.started`/`agent.finished` 事件：从 `payload` 中提取 `agent`、`display` 字段
- [x] 1.3 修复 `chatApi.ts` 的 `tool.started`/`tool.finished`/`tool.failed` 事件：从 `payload` 中提取 `tool_call_id`、`tool`、`arguments`、`result`、`error` 字段
- [x] 1.4 更新 `SseEvent` TypeScript 接口：增加 `payload` 字段的完整类型定义，与后端 `EventEnvelope` 结构对齐

## 2. IME 输入法守卫

- [x] 2.1 在 `InputBox.tsx` 中添加 `isComposing` ref 和 `compositionstart`/`compositionend` 事件处理
- [x] 2.2 修改 `handleKeyDown`：在 `isComposing.current === true` 时跳过 Enter 发送逻辑
- [x] 2.3 处理 Safari 兼容性：Safari 下 composition 期间 `keyCode === 229`，通过 `isComposing` ref 正确拦截

## 3. Tool 调用聚合展示

- [x] 3.1 重构 `ToolCallPanel.tsx`：将逐个渲染改为聚合面板，header 显示工具数量和整体状态，body 可折叠
- [x] 3.2 实现单 tool call 默认展开、多 tool call 默认折叠的逻辑
- [x] 3.3 实现 panel header 的聚合状态图标：全部 done（绿勾）、任一 running（旋转动画）、任一 failed（红叉）
- [x] 3.4 在 `MessageBubble.tsx` 中更新 ToolCallPanel 引用：保持 props 接口不变（仍接收 `toolCalls: ToolCall[]`）
- [x] 3.5 优化 tool call 更新时的 re-render：利用 Zustand selector 精确订阅 `messages[id].toolCalls`

## 4. Session 数据稳定回显

- [x] 4.1 在 `ChatInterface.tsx` 中将 `routeSessionId` 设为唯一渲染数据源，消息列表渲染完全基于 store
- [x] 4.2 修改 `useConversation.loadHistory`：增加 API 返回数据的字段映射逻辑（`toolCalls` JSON string 解析、缺失字段默认值）
- [x] 4.3 修复 history API 端点路径：确认 `GET /api/v1/history/{conversationId}` 可正确访问
- [x] 4.4 在 `chatStore.ts` 的 `loadHistory` 中增加数据合法性校验：过滤空 id、重复 id 的消息

## 5. 历史消息完整恢复

- [x] 5.1 确认 `GET /api/v1/history/{conversationId}` 返回的 `toolCalls` 字段包含完整字段（`id`、`name`、`arguments`、`status`、`result`）
- [x] 5.2 修复 `chatStore.loadHistory`：确保恢复后的消息 `status` 设为 `"done"`（历史消息不需要 streaming）
- [x] 5.3 处理 `images` 字段的恢复：MinIO URL 持久化后可直接用于 `<img>` 渲染

## 6. 集成验证

- [x] 6.1 手动测试：发送消息 → 等待 tool 调用完成 → 刷新页面 → 验证消息/tool/顺序完整一致
- [x] 6.2 手动测试：中文输入法下 Enter 选字不触发发送，英文下 Enter 正常发送
- [x] 6.3 手动测试：多 tool 调用场景下聚合面板折叠/展开正常，状态流转正确
- [x] 6.4 手动测试：切换 session 后 UI 正确清理并渲染新 session 数据
- [x] 6.5 运行现有 vitest 测试套件确认无回归
