## Context

当前 AI Chat 前端（`frontend/src/features/ai-chat/`）使用 React 18 + Zustand + TypeScript，通过 SSE 流式接收后端事件。代码探索发现以下关键事实：

1. **SSE 格式不匹配**：后端 `EventEnvelope` 将业务字段嵌套在 `payload` 中，前端 `chatApi.ts` 直接从顶层读取 `messageId`、`delta`、`toolCall`，导致事件无法正确解析
2. **无 IME 处理**：`InputBox.tsx` 的 `handleKeyDown` 仅检查 `e.key === 'Enter'`，无 `compositionstart`/`compositionend` 守卫
3. **Tool 调用平铺展示**：`ToolCallPanel.tsx` 对每个 tool call 渲染独立卡片，无按轮次聚合
4. **Session 仅存 localStorage**：`useSessions.ts` 将 session 列表存于客户端，刷新后依赖 history API 恢复

## Goals / Non-Goals

**Goals:**
- 修复前端 SSE 事件解析，正确读取 `EventEnvelope.payload.*` 中的字段
- 添加 IME composition 状态锁，防止中文输入法回车误触发
- Tool 调用按 assistant message 维度聚合为可折叠的 ToolExecutionPanel
- 刷新后通过 history API 完整恢复消息 + toolCalls + 顺序
- 基于 URL route sessionId 作为唯一渲染数据源

**Non-Goals:**
- 不修改后端 SSE 协议或 EventEnvelope 结构
- 不修改 session/memory 的后端机制
- 不引入新的状态管理库
- 不重构 legacy 组件（`components/ChatMessage.tsx` 等已标记 deprecated）

## Decisions

### Decision 1: SSE 解析层统一在 chatApi.ts 适配

**方案**：在 `handleEvent` 中增加 EventEnvelope 解包逻辑，从 `event.payload` 中提取 `messageId`、`delta`、`toolCall` 等字段，保持 store 接口不变。

**理由**：后端 EventEnvelope 结构不可改（架构约束），前端适配是最小改动路径。只需修改一个文件的解析逻辑，store 和组件无需感知 envelope 的存在。

**替代方案**：在 `sendChatMessage` 的 SSE 行解析阶段做 payload 展开 → 不选，因为会让 `SseEvent` 类型定义与实际线格式不一致，增加理解成本。

### Decision 2: IME 状态锁用 React state + event handler 实现

**方案**：在 `InputBox` 组件内使用 `useRef(isComposing)` 追踪 IME 状态，`compositionstart` 置 true，`compositionend` 置 false，`keydown` 检查 `isComposing.current` 跳过发送。

**理由**：IME composition 是浏览器原生事件，不需要引入第三方库。`useRef` 避免 composition 状态变化触发不必要的 re-render。

### Decision 3: Tool 聚合按 assistant message 维度

**方案**：在 `MessageBubble` 中新增 `ToolExecutionPanel` 组件，接收一整组 `ToolCall[]`，渲染为统一的可折叠面板。面板 header 显示工具数量和整体状态，展开后列出各 tool call 详情。

**理由**：同一 assistant message 的 toolCalls 已通过 `upsertToolCall` 关联到消息，自然形成聚合维度。不需要引入额外的 "turn" 概念。

### Decision 4: 历史恢复使用 re-fetch 策略

**方案**：`useConversation.loadHistory` 调用 `GET /api/v1/history/{conversationId}`，将返回的 messages 通过 `loadHistory` 直接写入 store。确保后端返回的数据包含完整的 `toolCalls`、`images`、`reasoning` 字段。

**理由**：后端已将消息持久化到 PostgreSQL，API 返回完整字段。前端只需正确映射字段即可恢复。不需要额外的 hydrate/diff 逻辑。

### Decision 5: Session 数据源统一为 route param

**方案**：`ChatInterface.tsx` 中 `routeSessionId`（来自 URL param `:id`）作为唯一 session 标识。`useEffect` 监听 `routeSessionId` 变化触发 `loadHistory`。`useSessions` hook 只管理 sidebar 显示的 session 列表，不参与消息渲染。

**理由**：URL 是天然的 single source of truth，浏览器前进/后退、刷新都能正确恢复。避免多处 state 同步问题。

## Risks / Trade-offs

- **[Risk] SSE 非标准行格式**：后端 `to_sse_data` 使用 `{"data": json_string}` 格式，前端按 `data:` 前缀解析。需确认 `data:` 后是 JSON 还是 `data: ` 空格后是 JSON → **Mitigation**：`chatApi.ts` 已有的 `trimmed.startsWith('data:')` 逻辑兼容两种格式
- **[Risk] 历史 API 返回的 toolCalls 可能是 JSON string**：数据库 `tool_calls` 列为 JSON 类型，但 `json.dumps` 后存储再读取可能是字符串 → **Mitigation**：`useConversation` 中增加 `typeof toolCalls === 'string' ? JSON.parse(toolCalls) : toolCalls` 防御性解析
- **[Trade-off] Tool 聚合后单条 tool 状态变化需更新整个 panel**：当前 Zustand selector 粒度是 message 级别，tool 状态更新触发整个 MessageBubble re-render → 可接受，tool 数量通常较少（<10 per message）
