## Why

当前聊天界面存在三个层面的技术债：消息模型混杂（role 包含 `tool_summary`/`agent_step`/`thinking` 等非标准角色）、SSE 事件协议私有化（`token`/`tool_start`/`tool_result` 命名不规范）、Chat UI 代码巨石化（ChatMessage.tsx 500+ 行杂糅所有渲染逻辑）。这些问题导致：新功能叠加困难、前后端协议耦合松散、与业界 AI Chat 标准交互体验差距大。本次改造以标准化 Message Model 和 SSE 协议为核心，建立可持续演进的 AI Chat UI 专用层。

## What Changes

- **BREAKING**: 重构前端 Message 模型，role 统一为 `user` | `assistant` | `system`，新增 `reasoning`、`toolCalls`、`status`、`agentId` 字段
- **BREAKING**: SSE 事件协议重命名为 `message.delta`、`message.tool_call`、`message.reasoning`、`message.done`
- 前端新增 `/src/features/ai-chat/` 独立模块，完全自定义 Chat UI（不再使用 Ant Design 聊天组件）
- 引入 Zustand 状态管理替代散落的 useState，支持流式高频更新
- 升级代码高亮为 Shiki，替换 highlight.js
- 新增 MessageList 虚拟滚动，支持 1000+ 消息量级
- 新增 Agent 选择器（Chat Header 左侧），支持动态多 Agent 切换
- Spring Boot 新增 `/api/agents` CRUD 代理接口，新增 agentId 透传
- Python AI Service 的 GenerateRequest 新增 agentId 字段，支持 Agent 路由
- 消息历史持久化到数据库统一管理

## Capabilities

### New Capabilities
- `chat-message-protocol`: 统一前后端 Message Model（标准 role + reasoning + toolCalls + status + agentId）
- `sse-event-protocol`: 标准化 SSE 事件协议（message.delta / message.tool_call / message.reasoning / message.done）
- `ai-chat-ui`: 独立 AI Chat UI 模块（MessageBubble / ReasoningPanel / ToolCallPanel / MarkdownRenderer / 虚拟滚动 / Shiki 代码高亮）
- `agent-gateway`: Spring Boot Agent CRUD 代理 + agentId 透传 + Agent 路由
- `agent-chat-routing`: Python AI Service 根据 agentId 路由不同 Agent，输出符合新 Message Model 的 SSE 事件

### Modified Capabilities
<!-- 本次不修改已有 spec（现有 spec 均为工具系统相关，不影响） -->

## Impact

- **前端**: `src/types/chat.ts` 完全重写；`src/pages/ChatInterface.tsx` 替换为新的 ChatContainer；`src/components/ChatMessage.tsx` 拆分为多个独立组件；新增 Zustand store
- **后端**: `ChatRequest.java` 新增 agentId；`ChatController.java` 新增 Agent CRUD 端点；`AIClient.java` 透传 agentId
- **Python**: `GenerateRequest` schema 新增 agentId；`chat.py` 新增 agent 路由逻辑；`event_envelope.py` 新增 message.delta/message.tool_call/message.reasoning/message.done 事件类型
- **数据库**: 新增消息历史持久化表（复用 PostgreSQL）
- **依赖**: 前端新增 zustand、shiki、@tanstack/react-virtual；Python 无新依赖
