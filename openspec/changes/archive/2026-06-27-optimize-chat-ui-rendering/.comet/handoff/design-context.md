# Comet Design Handoff

- Change: optimize-chat-ui-rendering
- Phase: design
- Mode: compact
- Context hash: 16a30a8acdb87974086e996ad3be4033e5b2cfcbc028409b8bbdefcc48ea0cf8

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/optimize-chat-ui-rendering/proposal.md

- Source: openspec/changes/optimize-chat-ui-rendering/proposal.md
- Lines: 1-28
- SHA256: c8305693f901ae706fa9f130b3f46761df452b3580a12fd718ac66cd12a89e79

```md
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
```

## openspec/changes/optimize-chat-ui-rendering/design.md

- Source: openspec/changes/optimize-chat-ui-rendering/design.md
- Lines: 1-63
- SHA256: 9a19fb0ae5c18f42db7a49ad43c967707d2e85b44e534bf4da896e30e86059ea

```md
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
```

## openspec/changes/optimize-chat-ui-rendering/tasks.md

- Source: openspec/changes/optimize-chat-ui-rendering/tasks.md
- Lines: 1-41
- SHA256: e82fdc2baa69ce165c6e349e98cac3da4436226df94a5bac3e72a33742bdc0bd

```md
## 1. SSE 事件解析修复

- [ ] 1.1 修复 `chatApi.ts` 的 `handleEvent` 函数：从 `event.payload` 中提取 `messageId`、`delta`、`toolCall` 等业务字段，兼容 flat 格式 fallback
- [ ] 1.2 修复 `chatApi.ts` 的 `agent.started`/`agent.finished` 事件：从 `payload` 中提取 `agent`、`display` 字段
- [ ] 1.3 修复 `chatApi.ts` 的 `tool.started`/`tool.finished`/`tool.failed` 事件：从 `payload` 中提取 `tool_call_id`、`tool`、`arguments`、`result`、`error` 字段
- [ ] 1.4 更新 `SseEvent` TypeScript 接口：增加 `payload` 字段的完整类型定义，与后端 `EventEnvelope` 结构对齐

## 2. IME 输入法守卫

- [ ] 2.1 在 `InputBox.tsx` 中添加 `isComposing` ref 和 `compositionstart`/`compositionend` 事件处理
- [ ] 2.2 修改 `handleKeyDown`：在 `isComposing.current === true` 时跳过 Enter 发送逻辑
- [ ] 2.3 处理 Safari 兼容性：Safari 下 composition 期间 `keyCode === 229`，通过 `isComposing` ref 正确拦截

## 3. Tool 调用聚合展示

- [ ] 3.1 重构 `ToolCallPanel.tsx`：将逐个渲染改为聚合面板，header 显示工具数量和整体状态，body 可折叠
- [ ] 3.2 实现单 tool call 默认展开、多 tool call 默认折叠的逻辑
- [ ] 3.3 实现 panel header 的聚合状态图标：全部 done（绿勾）、任一 running（旋转动画）、任一 failed（红叉）
- [ ] 3.4 在 `MessageBubble.tsx` 中更新 ToolCallPanel 引用：保持 props 接口不变（仍接收 `toolCalls: ToolCall[]`）
- [ ] 3.5 优化 tool call 更新时的 re-render：利用 Zustand selector 精确订阅 `messages[id].toolCalls`

## 4. Session 数据稳定回显

- [ ] 4.1 在 `ChatInterface.tsx` 中将 `routeSessionId` 设为唯一渲染数据源，消息列表渲染完全基于 store
- [ ] 4.2 修改 `useConversation.loadHistory`：增加 API 返回数据的字段映射逻辑（`toolCalls` JSON string 解析、缺失字段默认值）
- [ ] 4.3 修复 history API 端点路径：确认 `GET /api/v1/history/{conversationId}` 可正确访问
- [ ] 4.4 在 `chatStore.ts` 的 `loadHistory` 中增加数据合法性校验：过滤空 id、重复 id 的消息

## 5. 历史消息完整恢复

- [ ] 5.1 确认 `GET /api/v1/history/{conversationId}` 返回的 `toolCalls` 字段包含完整字段（`id`、`name`、`arguments`、`status`、`result`）
- [ ] 5.2 修复 `chatStore.loadHistory`：确保恢复后的消息 `status` 设为 `"done"`（历史消息不需要 streaming）
- [ ] 5.3 处理 `images` 字段的恢复：MinIO URL 持久化后可直接用于 `<img>` 渲染

## 6. 集成验证

- [ ] 6.1 手动测试：发送消息 → 等待 tool 调用完成 → 刷新页面 → 验证消息/tool/顺序完整一致
- [ ] 6.2 手动测试：中文输入法下 Enter 选字不触发发送，英文下 Enter 正常发送
- [ ] 6.3 手动测试：多 tool 调用场景下聚合面板折叠/展开正常，状态流转正确
- [ ] 6.4 手动测试：切换 session 后 UI 正确清理并渲染新 session 数据
- [ ] 6.5 运行现有 vitest 测试套件确认无回归
```

## openspec/changes/optimize-chat-ui-rendering/specs/ai-chat-ui/spec.md

- Source: openspec/changes/optimize-chat-ui-rendering/specs/ai-chat-ui/spec.md
- Lines: 1-69
- SHA256: 26c7db60e708bb711d8acfb9a657b1034adc56520b910737956e8906648abfd1

```md
## MODIFIED Requirements

### Requirement: ToolCallPanel
系统 SHALL 提供 ToolCallPanel 组件，将同一消息的所有 tool calls 聚合展示在一个可折叠的执行面板中，支持状态流转和展开详情。

#### Scenario: Aggregated tool calls display (collapsed)
- **WHEN** 消息包含 1 个或多个 toolCalls
- **AND** 面板处于折叠状态
- **THEN** 显示统一的面板 header，包含工具数量摘要（如"工具调用 (3)"）和整体执行状态图标
- **AND** 状态图标：全部 done 显示绿色勾、任一 running 显示旋转动画、任一 failed 显示红色叉

#### Scenario: Aggregated tool calls display (expanded)
- **WHEN** 用户点击折叠面板展开
- **THEN** 显示所有 tool call 的执行列表，每条包含：工具名称、状态图标、执行耗时（如有）
- **AND** 已完成的 tool call 可进一步展开查看 result 详情

#### Scenario: Streaming tool status update
- **WHEN** SSE 事件更新某个 tool call 的状态（running → done）
- **THEN** 面板内对应 tool call 的状态图标实时更新
- **AND** 面板 header 的整体状态图标同步更新

#### Scenario: Running tool display
- **WHEN** 工具调用状态为 "running" 或 "pending"
- **THEN** 显示工具名称 + 旋转加载动画 + "执行中..." 文字

#### Scenario: Completed tool display
- **WHEN** 工具调用状态为 "done"
- **THEN** 显示工具名称 + 绿色完成标记 + 可展开查看结果详情

#### Scenario: Failed tool display
- **WHEN** 工具调用状态为 "failed"
- **THEN** 显示工具名称 + 红色失败标记 + 错误信息

#### Scenario: Single tool call no collapse needed
- **WHEN** 消息仅包含 1 个 toolCall
- **THEN** 面板默认展开，显示 tool 名称和执行状态
- **AND** 不显示折叠/展开按钮

### Requirement: MessageList Session Hydration
系统 SHALL 在 MessageList 渲染时完全基于 Zustand store 中的 `messageOrder` 和 `messages` 字典渲染，不依赖组件局部 state 或缓存。

#### Scenario: Messages derived from store
- **WHEN** MessageList 渲染消息列表
- **THEN** 消息顺序严格基于 `messageOrder` 数组
- **AND** 每条消息内容严格基于 `messages[id]` 字典
- **AND** 不依赖任何局部 state 或 sessionStorage

#### Scenario: Session switch clears and reloads
- **WHEN** 用户从 Session A 切换到 Session B
- **THEN** 系统先 clearMessages 清空 store
- **AND** 然后 loadHistory 加载 Session B 的历史消息
- **AND** UI 在短暂空白后渲染 Session B 的消息

## ADDED Requirements

### Requirement: Session-Based Rendering
系统 SHALL 以 URL route param `:id`（sessionId）作为消息渲染的唯一数据源标识。ChatInterface 页面监听 route param 变化触发数据加载。

#### Scenario: URL-driven session loading
- **WHEN** 浏览器导航到 `/chat/:id`
- **THEN** ChatInterface 读取 `:id` 作为当前 sessionId
- **AND** 调用 `loadHistory(:id)` 加载该 session 的消息
- **AND** store 中的 conversationId 同步更新为 `:id`

#### Scenario: Refresh preserves session context
- **WHEN** 用户在 `/chat/abc123` 刷新页面
- **THEN** 系统重新读取 URL param `abc123`
- **AND** 调用 history API 加载 session `abc123` 的消息
- **AND** 侧边栏显示该 session 为 active 状态
```

## openspec/changes/optimize-chat-ui-rendering/specs/chat-history-restore/spec.md

- Source: openspec/changes/optimize-chat-ui-rendering/specs/chat-history-restore/spec.md
- Lines: 1-35
- SHA256: df77116d5c82d912fda998a074e86edc6a2c9900db6d24f78acc036be2ea24c3

```md
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
```

## openspec/changes/optimize-chat-ui-rendering/specs/ime-input-guard/spec.md

- Source: openspec/changes/optimize-chat-ui-rendering/specs/ime-input-guard/spec.md
- Lines: 1-43
- SHA256: e1baa65fc231f06dfc137a72b5f149c5b1d44dd9ddf47ecdaf4500638f824ac7

```md
## ADDED Requirements

### Requirement: IME Composition State Lock
系统 SHALL 在 InputBox 组件中监听 `compositionstart` 和 `compositionend` 事件，维护 `isComposing` 状态锁。当 IME 处于组合输入状态时，Enter 键不触发消息发送。

#### Scenario: IME composition prevents send
- **WHEN** 用户使用中文/日文/韩文输入法输入文字
- **AND** IME 组合窗口处于激活状态（compositionstart 已触发，compositionend 未触发）
- **AND** 用户按下 Enter 键确认候选字
- **THEN** 系统不触发消息发送
- **AND** Enter 事件由 IME 处理（选字确认）

#### Scenario: Enter sends when not composing
- **WHEN** 用户输入英文或已完成中文输入
- **AND** IME 组合窗口未激活（isComposing === false）
- **AND** 用户按下 Enter 键（非 Shift+Enter）
- **THEN** 系统触发消息发送

#### Scenario: Shift+Enter inserts newline during composition
- **WHEN** IME 处于组合输入状态
- **AND** 用户按下 Shift+Enter
- **THEN** 系统在输入框中插入换行符（不发送消息）

### Requirement: IME State Isolation
系统 SHALL 使用 `useRef` 存储 `isComposing` 状态，避免 composition 状态变化触发不必要的组件 re-render。

#### Scenario: Composition state changes don't cause re-render
- **WHEN** IME composition 状态在 true/false 之间切换
- **THEN** InputBox 组件不发生 re-render
- **AND** 输入框的光标位置和候选窗口不受影响

### Requirement: Cross-Browser IME Compatibility
系统 SHALL 确保 IME 守卫逻辑在主流浏览器（Chrome、Firefox、Safari、Edge）上行为一致。

#### Scenario: Chrome IME behavior
- **WHEN** 在 Chrome 中使用拼音输入法
- **AND** `compositionstart` 和 `compositionend` 事件按规范触发
- **THEN** Enter 键在 composition 期间不发送消息

#### Scenario: Safari IME behavior
- **WHEN** 在 Safari 中使用中文输入法
- **AND** Safari 的 `keydown` 事件在 composition 期间 `keyCode` 为 229
- **THEN** 系统通过 `isComposing` ref 正确阻止发送
```

## openspec/changes/optimize-chat-ui-rendering/specs/sse-event-protocol/spec.md

- Source: openspec/changes/optimize-chat-ui-rendering/specs/sse-event-protocol/spec.md
- Lines: 1-31
- SHA256: 8f5a43c7f0f8f76bebe7c7651b8277d4ffaa52efc538a117aafc20512be14377

```md
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
```

