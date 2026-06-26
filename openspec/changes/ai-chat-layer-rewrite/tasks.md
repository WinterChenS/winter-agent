## 1. Python AI Service — 协议层升级

- [x] 1.1 重构 `domain/event_envelope.py`：新增 `envelope_message_delta`、`envelope_message_tool_call`、`envelope_message_reasoning`、`envelope_message_done` 事件构建函数，保留 `envelope_error`
- [x] 1.2 更新 `api/events/event_mapper.py`：将 LangGraph 事件映射改为新协议（token → message.delta, tool_start/tool_result → message.tool_call, reasoning_delta → message.reasoning），为每个事件添加 `messageId` 和 `agentId`
- [x] 1.3 更新 `api/schemas.py`：`GenerateRequest` 新增 `agentId?: str` 字段
- [x] 1.4 更新 `api/routes/chat.py`：`stream_generate` 根据 agentId 加载 Agent 定义并注入 `active_agent`；在流开始时生成 messageId；在流结束时发送 `message.done`
- [ ] 1.5 新增 `db/chat_message_repository.py`：实现 `chat_messages` 表的 CRUD（create/update/getByConversation）
- [ ] 1.6 新增 PostgreSQL 迁移脚本：创建 `chat_messages` 表
- [ ] 1.7 更新 `api/routes/chat.py` 的 `get_chat_history`：返回新 Message Model 格式（含 reasoning/toolCalls/agentId/status）

## 2. Python AI Service — Agent 路由增强

- [ ] 2.1 更新 `graph/graph.py`：在 graph state 初始化时读取 `active_agent` 字段，支持按 agentId 选择对应 Agent Node
- [ ] 2.2 验证 RouterAgent 在收到 active_agent 时直接路由到对应 Agent（不经过关键词匹配）

## 3. Spring Boot — Agent 网关

- [ ] 3.1 新增 `AgentController.java`：实现 `GET/POST/PUT/DELETE /api/agents`，代理转发到 Python `/api/v1/agents/`
- [ ] 3.2 更新 `ChatRequest.java`：新增 `agentId` 字段
- [ ] 3.3 更新 `AIClient.java`：`streamGenerate` 方法透传 agentId 到 Python

## 4. 前端 — 类型与基础设施

- [ ] 4.1 重写 `frontend/src/types/chat.ts`：使用新 Message/ToolCall 类型定义（role 为 user|assistant|system，新增 reasoning/toolCalls/status/agentId）
- [ ] 4.2 安装依赖：`zustand`、`@tanstack/react-virtual`、`shiki`
- [ ] 4.3 新增 `frontend/src/features/ai-chat/types/message.ts`：导出 Message、ToolCall 类型
- [ ] 4.4 新增 `frontend/src/features/ai-chat/store/chatStore.ts`：Zustand store（messages, addMessage, updateMessage, appendDelta, upsertToolCall, appendReasoning, setMessageStatus, agentId, setAgentId, conversationId）
- [ ] 4.5 新增 `frontend/src/features/ai-chat/services/chatApi.ts`：封装 SSE fetch 请求（POST /api/chat，含 agentId），解析新事件协议（message.delta/tool_call/reasoning/done）

## 5. 前端 — 核心组件

- [ ] 5.1 新增 `ChatContainer.tsx`：顶层布局（Header + MessageList + InputBox），集成 Agent 选择器
- [ ] 5.2 新增 `MessageList.tsx`：使用 `@tanstack/react-virtual` 实现虚拟滚动，自动滚动/用户覆盖逻辑
- [ ] 5.3 新增 `MessageBubble.tsx`：用户右对齐蓝色气泡，AI 左对齐灰色气泡，显示 Agent 标识，渲染 Markdown + 图表
- [ ] 5.4 新增 `ReasoningPanel.tsx`：可折叠推理面板，支持 Markdown 渲染
- [ ] 5.5 新增 `ToolCallPanel.tsx`：可折叠工具调用卡片（工具名 + 参数 + 状态图标 + 结果详情，支持 running/done/failed 三态动画）
- [ ] 5.6 新增 `MarkdownRenderer.tsx`：集成 react-markdown + Shiki 代码高亮 + LaTeX 支持 + 表格/引用渲染
- [ ] 5.7 新增 `StreamingRenderer.tsx`：流式内容渲染容器（增量渲染、闪烁光标动画）
- [ ] 5.8 新增 `InputBox.tsx`：文本输入框 + 发送按钮 + loading 状态禁用

## 6. 前端 — 集成与迁移

- [ ] 6.1 新增 `frontend/src/features/ai-chat/hooks/useChatStream.ts`：基于 chatStore + chatApi 的流式对话 hook
- [ ] 6.2 新增 `frontend/src/features/ai-chat/hooks/useConversation.ts`：会话管理 hook（加载历史、创建会话）
- [ ] 6.3 更新 `App.tsx` 路由：Chat 页面路由指向新 ChatContainer
- [ ] 6.4 废弃旧 ChatMessage.tsx / ChatInput.tsx / useChat.ts（保留文件不删，移除路由引用）
- [ ] 6.5 清理旧的 MessageList.tsx 引用

## 7. 测试与验证

- [ ] 7.1 更新 `scripts/test_chat_scenarios.py`：适配新 SSE 事件协议
- [ ] 7.2 编写前端单元测试：chatStore actions（addMessage/updateMessage/appendDelta 等）
- [ ] 7.3 E2E 测试：Agent 选择 → 发送消息 → 流式接收 → 消息完成全链路
- [ ] 7.4 验收检查：对照验收标准逐项确认
