## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Active Agent Status Display
聊天 Header SHALL 实时展示当前活跃 Agent 的图标和名称，基于 SSE agent.started / agent.finished 事件动态切换。

#### Scenario: Agent started event triggers display
- **WHEN** SSE 收到 `agent.started` 事件（含 agentId 和 display_name）
- **THEN** Header 显示该 Agent 的图标和 display_name，并显示状态文字（如 "Thinking..."）

#### Scenario: Agent finished event clears status
- **WHEN** SSE 收到 `agent.finished` 事件
- **THEN** Header 清除临时状态文字，恢复只显示 Agent 图标和名称

#### Scenario: Multi-agent chain display
- **WHEN** 多个 Agent 按顺序启动和完成
- **THEN** Header 依次显示每个 Agent 的状态，上一 Agent 完成后更新为下一 Agent

### Requirement: Sidebar Integration
ChatInterface SHALL 集成新的 ChatGPT 风格侧边栏，替换旧版 session-list 侧边栏。

#### Scenario: Sidebar renders in ChatInterface
- **WHEN** ChatInterface 加载
- **THEN** 新的 Sidebar 组件显示，包含顶部分组导航和 Recent Chats 列表

#### Scenario: Sidebar responsive on mobile
- **WHEN** 视口宽度 < 768px
- **THEN** Sidebar 默认隐藏，点击汉堡菜单按钮滑入显示，带半透明遮罩
