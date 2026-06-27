# ai-chat-ui Specification

## Purpose
TBD - created by archiving change ai-chat-layer-rewrite. Update Purpose after archive.
## Requirements
### Requirement: ChatContainer Layout
系统 SHALL 提供 ChatContainer 作为聊天界面的顶层容器，包含 Header（Agent 选择器 + 会话信息）、MessageList（消息列表）、InputBox（输入区域）三个区域。

#### Scenario: Chat page layout
- **WHEN** 用户进入聊天页面
- **THEN** 页面展示 Header（顶部）、MessageList（中间填充）、InputBox（底部固定）三区域布局

### Requirement: Agent Selector
系统 SHALL 在 Chat Header 提供 Agent 下拉选择器，支持切换当前对话的 Agent。

#### Scenario: Select an agent
- **WHEN** 用户从 Agent 选择器中选择一个 Agent
- **THEN** 后续消息携带该 agentId，消息气泡中显示 Agent 标识

#### Scenario: Filter disabled agents
- **WHEN** 某些 Agent 被禁用（enabled: false）
- **THEN** 这些 Agent 不在选择器中显示

#### Scenario: Agent identity in message
- **WHEN** AI 回复由特定 Agent 处理
- **THEN** 该消息气泡显示 Agent 名称/标识（如 "🔍 Search Agent"）

### Requirement: MessageBubble
系统 SHALL 提供 MessageBubble 组件，根据 role 渲染不同样式：用户消息右对齐蓝色气泡，AI 消息左对齐灰色气泡。

#### Scenario: User message bubble
- **WHEN** 渲染 role 为 "user" 的消息
- **THEN** 气泡右对齐，蓝色背景，显示 content 纯文本

#### Scenario: Assistant message bubble
- **WHEN** 渲染 role 为 "assistant" 的消息
- **THEN** 气泡左对齐，灰色/白色背景，显示 Markdown 渲染后的 content

### Requirement: ReasoningPanel
系统 SHALL 提供 ReasoningPanel 组件，以可折叠面板展示 AI 的思考过程（reasoning 字段）。

#### Scenario: Collapsed reasoning display
- **WHEN** 消息包含 reasoning 且面板折叠
- **THEN** 显示"思考过程 (N 步)"标题，点击可展开

#### Scenario: Expanded reasoning display
- **WHEN** 用户点击展开推理面板
- **THEN** 展示完整的推理内容，支持 Markdown 渲染

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

### Requirement: Markdown Renderer
系统 SHALL 提供 Markdown 渲染组件，支持：段落、列表、表格、代码块（Shiki 高亮）、LaTeX 公式、引用块。

#### Scenario: Code block with syntax highlighting
- **WHEN** Markdown 包含代码块
- **THEN** 使用 Shiki 进行语法高亮，显示行号和复制按钮

#### Scenario: Table rendering
- **WHEN** Markdown 包含表格
- **THEN** 渲染带边框和斑马纹的表格，横向溢出时滚动

### Requirement: Virtual Scrolling
系统 SHALL 使用 @tanstack/react-virtual 实现 MessageList 虚拟滚动，支持 1000+ 消息的流畅渲染。

#### Scenario: Long conversation performance
- **WHEN** 会话包含 1000 条消息
- **THEN** 页面只渲染可视区域内的消息，滚动流畅无卡顿

### Requirement: Auto Scroll with User Override
系统 SHALL 在流式输出时自动滚动到底部；若用户手动向上滚动查看历史，则暂停自动滚动，直到用户重新滚动到底部。

#### Scenario: Auto-scroll during streaming
- **WHEN** AI 正在流式输出且用户在底部
- **THEN** 新内容到达时自动滚动到底部

#### Scenario: User scroll override
- **WHEN** AI 正在流式输出且用户向上滚动超过 100px
- **THEN** 暂停自动滚动，显示"回到底部"浮动按钮

### Requirement: Streaming Animation
系统 SHALL 在 AI 消息处于 "streaming" 状态时显示打字光标动画（闪烁竖线）。

#### Scenario: Typing indicator during streaming
- **WHEN** 消息 status 为 "streaming" 且 content 非空
- **THEN** 在文本末尾显示闪烁光标动画

### Requirement: Message Status Display
系统 SHALL 根据消息 status 展示对应状态：done 无标记，streaming 显示动画，error 显示红色错误信息 + 重试按钮。

#### Scenario: Error message with retry
- **WHEN** 消息 status 为 "error"
- **THEN** 显示错误提示和"重新发送"按钮

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

