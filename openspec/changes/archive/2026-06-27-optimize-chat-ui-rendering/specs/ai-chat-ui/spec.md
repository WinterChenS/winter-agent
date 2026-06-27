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

## ADDED Requirements

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
