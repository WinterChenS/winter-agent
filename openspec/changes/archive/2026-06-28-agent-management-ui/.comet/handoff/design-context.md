# Comet Design Handoff

- Change: agent-management-ui
- Phase: design
- Mode: compact
- Context hash: dff20f5fb9d52ef60d6b143edf5d936b54ffff517ff73a3da993db88ad7fd304

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/agent-management-ui/proposal.md

- Source: openspec/changes/agent-management-ui/proposal.md
- Lines: 1-32
- SHA256: e25bc987a4789d654268e4352e25ba3267819b01b7c50e6976937d786926f616

```md
## Why

当前侧边栏仅有聊天历史列表，缺少结构化导航。Agent 管理页面是旧版 table 风格，体验差。聊天页面缺少当前 Agent 的实时状态展示。前端需要升级为 ChatGPT 风格的企业级 AI Agent 管理体验。

## What Changes

- **侧边栏**: 顶部固定导航（AI Studio / New Chat / Agents）+ 底部 Recent Chats（Today/Yesterday 分组），仅聊天列表滚动
- **Agent 管理页**: 替换 /admin/agents 为 Card 布局，支持搜索/分页/排序/启停，Hover 动效
- **Agent 编辑器**: Drawer 打开，分组展示 Basic/Prompt(CodeMirror 6)/Model/Tools/Trigger/Advanced
- **聊天 Agent 状态**: 聊天顶部实时显示当前 Agent 图标+名称，基于 SSE 事件驱动
- **安全**: model_config 通过后端接口安全获取，前端不处理敏感凭证
- **CodeMirror 6**: 作为 Prompt 编辑器，支持 Markdown、复制、自动换行、全屏

## Capabilities

### New Capabilities
- `sidebar-navigation`: ChatGPT 风格侧边栏导航（固定顶部分组 + Recent Chats 滚动）
- `agent-management-page`: Agent 管理页面（Card 布局 + 搜索/分页/排序 + Drawer 编辑器）
- `prompt-editor`: CodeMirror 6 系统提示词编辑器组件

### Modified Capabilities
- `ai-chat-ui`: 新增侧边栏导航需求 + 聊天 Agent 状态实时展示需求

## Impact

- `frontend/src/components/Sidebar.tsx` — 重写为 ChatGPT 风格导航
- `frontend/src/pages/AdminAgents.tsx` — 删除，替换为 AgentManagement 页面
- `frontend/src/pages/ChatInterface.tsx` — 集成新 Sidebar + Agent 状态展示
- `frontend/src/features/ai-chat/` — 新增 Agent 状态相关 store 字段
- `frontend/src/views/AgentManagement/` — 新增
- `frontend/src/components/AgentCard.vue` — 应为 .tsx（React）
- `frontend/package.json` — 新增 codemirror 依赖
```

## openspec/changes/agent-management-ui/design.md

- Source: openspec/changes/agent-management-ui/design.md
- Lines: 1-45
- SHA256: ba5d880550d71314bd0874eb800d2dfe45dfaeb1d3bcf7b7fff84fe8b5af8053

```md
## Context

前端当前仅有旧版 table 风格 AdminAgents 页面和简单 session-list 侧边栏。后端 `agent-backend-proxy` 已提供 8 个 REST 端点（CRUD + enable/disable/clone），前端可直接调用。

## Goals / Non-Goals

**Goals:**
- 侧边栏升级为 ChatGPT 风格固定导航 + Recent Chats
- Agent 管理页替换为 Card 布局 + Drawer 编辑器
- Prompt 编辑器使用 CodeMirror 6
- 聊天页面实时展示 Agent 状态

**Non-Goals:**
- 不修改后端（Python/SpringBoot）
- 不修改数据库
- 不修改 SSE 协议
- 不做 MCP/Tools/Knowledge 等预留功能的实际实现

## Decisions

### Decision 1: 保留现有路由结构
**选择**: 新增 `/agents` 路由替换 `/admin/agents`，保留 `/` 和 `/chat/:id` 不变
**理由**: 最小化路由变更，不影响已有聊天功能

### Decision 2: 前端数据获取
**选择**: 使用自定义 `useAgent` composable hook + `fetch()` API，与现有模式一致（无 axios、无 React Query）
**理由**: 保持项目代码风格统一

### Decision 3: Drawer 实现
**选择**: 纯 Tailwind CSS 实现 Drawer（fixed right-0 + translate-x + 遮罩），无额外依赖
**理由**: 项目无组件库，用 Tailwind 可保持轻量；类似 ChatGPT 的侧边栏动画逻辑

### Decision 4: 模型配置安全
**选择**: `model_config` 字段通过 SpringBoot `GET /api/agents` 正常返回（不含敏感凭证），前端 Drawer 中直接编辑 `temperature`/`top_p`/`max_tokens`/`model_name` 等字段，写入 `model_config` JSONB
**理由**: 真正的 API key 存储在服务端 `.env`，model_config 不含敏感信息

### Decision 5: Agent 状态展示
**选择**: 扩展 Zustand store 的 `activeAgent`/`agentStatus` 字段，在 Chat Header 中展示
**理由**: 已有 agent.started/agent.finished SSE 事件处理，只需 UI 渲染

## Risks / Trade-offs

- **[Risk] React 项目用 `.vue` 文件** → 已纠正，全部使用 `.tsx`
- **[Risk] CodeMirror 6 bundle size** → 支持 Tree-shaking，按需导入语言包
- **[Risk] 侧边栏 Session 分组性能** → 使用 `useMemo` 缓存分组结果
```

## openspec/changes/agent-management-ui/tasks.md

- Source: openspec/changes/agent-management-ui/tasks.md
- Lines: 1-39
- SHA256: 0e6801b38bd6076125aafc796df005478244e4d815a35e50cfebbc827e4e4145

```md
## 1. Sidebar Navigation

- [ ] 1.1 Rewrite `Sidebar.tsx` as ChatGPT-style navigation (top fixed nav + Recent Chats)
- [ ] 1.2 Add Today/Yesterday grouping for Recent Chats
- [ ] 1.3 Add future-slot menu items (Tools, Knowledge, MCP, Settings) with locked styling
- [ ] 1.4 Integrate new Sidebar into `ChatInterface.tsx`

## 2. Agent Management Page

- [ ] 2.1 Create `useAgent.ts` composable hook (fetch agents, CRUD, enable/disable, clone)
- [ ] 2.2 Create `agent.ts` API service (wraps fetch calls to /api/agents endpoints)
- [ ] 2.3 Create `AgentCard.tsx` component (card layout with icon, name, tags, status)
- [ ] 2.4 Create `AgentManagement` page at `/agents` route (search, pagination, sorting, loading, empty state)
- [ ] 2.5 Create `AgentStatus.tsx` component (enabled/disabled toggle badge)
- [ ] 2.6 Add `/agents` route to `App.tsx`

## 3. Agent Drawer Editor

- [ ] 3.1 Create `AgentDrawer.tsx` component (right-side drawer with overlay)
- [ ] 3.2 Create Basic Info section (name, display_name, description, icon, agent_type, tags, priority, enabled)
- [ ] 3.3 Create `PromptEditor.tsx` using CodeMirror 6 (Markdown mode, word wrap, copy, fullscreen)
- [ ] 3.4 Install codemirror dependencies (`@codemirror/view`, `@codemirror/state`, `@codemirror/lang-markdown`, `@codemirror/commands`)
- [ ] 3.5 Create Model section (model_name, temperature, top_p, max_tokens, streaming, json_mode in model_config)
- [ ] 3.6 Create `ToolSelector.tsx` component (multi-select checkboxes with tool names)
- [ ] 3.7 Create `TagInput.tsx` component (tag input with Enter to add, click to remove)
- [ ] 3.8 Create Trigger section (trigger_keywords via TagInput)
- [ ] 3.9 Create Advanced section (collaboration_strategy)

## 4. Chat Agent Status

- [ ] 4.1 Extend chat Zustand store with `activeAgentDisplay` field (icon + display_name)
- [ ] 4.2 Render active Agent status in Chat Header (icon + name + status text)
- [ ] 4.3 Update agent status on SSE `agent.started` / `agent.finished` events

## 5. Cleanup

- [ ] 5.1 Delete old `AdminAgents.tsx` page
- [ ] 5.2 Remove old `/admin/agents` route from `App.tsx`
- [ ] 5.3 Verify existing chat, SSE, Markdown, and agent selector functionality is unaffected
```

## openspec/changes/agent-management-ui/specs/agent-management-page/spec.md

- Source: openspec/changes/agent-management-ui/specs/agent-management-page/spec.md
- Lines: 1-62
- SHA256: f2c94eaaf3e1af3bdba710544afbfce0fd9dbb17e9a01aa7f7392a6d5fc5c30f

```md
## ADDED Requirements

### Requirement: Agent Management Page
The system SHALL provide an Agent Management page at `/agents` with Card-based layout, search, pagination, and sorting capabilities.

#### Scenario: Card layout displays agents
- **WHEN** user navigates to `/agents`
- **THEN** agents are displayed as Cards (not table rows), each showing icon, name, agent_type, tags, and enabled status

#### Scenario: Empty state
- **WHEN** no agents exist
- **THEN** page shows an empty state illustration with "Create your first agent" prompt

#### Scenario: Loading state
- **WHEN** agents are being fetched
- **THEN** skeleton cards are displayed as placeholders

#### Scenario: Search agents
- **WHEN** user types in the search input
- **THEN** the agent list is filtered by name or display_name

#### Scenario: Pagination
- **WHEN** there are more than the page size agents
- **THEN** pagination controls appear allowing navigation between pages

#### Scenario: Hover effect
- **WHEN** user hovers over an agent card
- **THEN** the card elevates with shadow and shows action buttons (Edit, Clone, Enable/Disable, Delete)

### Requirement: Agent Enable/Disable Toggle
The system SHALL support enabling and disabling agents directly from the management page.

#### Scenario: Disable an agent
- **WHEN** user clicks disable on an enabled agent
- **THEN** the agent's enabled status toggles to false and the card updates

#### Scenario: Enable an agent
- **WHEN** user clicks enable on a disabled agent
- **THEN** the agent's enabled status toggles to true and the card updates

### Requirement: Agent Drawer Editor
The system SHALL open a Drawer (not Modal) when editing or creating an agent, with grouped sections: Basic Info, Prompt, Model, Tools, Trigger, Advanced.

#### Scenario: Create new agent
- **WHEN** user clicks "+ New Agent" button
- **THEN** a Drawer opens from the right with an empty form

#### Scenario: Edit existing agent
- **WHEN** user clicks "Edit" on an agent card
- **THEN** a Drawer opens with the agent's data pre-filled

#### Scenario: Drawer sections
- **WHEN** the Drawer is open
- **THEN** it shows collapsible sections: Basic Info (name/icon/description), Prompt (CodeMirror editor), Model (model_name/temperature/top_p/max_tokens/streaming), Tools (multi-select checkboxes), Trigger (tag input), Advanced (collaboration_strategy/priority)

#### Scenario: Delete agent
- **WHEN** user clicks "Delete" on an agent card
- **THEN** a confirmation dialog appears, and upon confirmation the agent is deleted

#### Scenario: Clone agent
- **WHEN** user clicks "Clone" on an agent card
- **THEN** the agent is cloned via the API and a new card appears in the list
```

## openspec/changes/agent-management-ui/specs/ai-chat-ui/spec.md

- Source: openspec/changes/agent-management-ui/specs/ai-chat-ui/spec.md
- Lines: 1-44
- SHA256: 3fac81beb6b76d07064ad6c59fe14697bf7a2e56637eabcf279bd6d0575979cf

```md
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
```

## openspec/changes/agent-management-ui/specs/prompt-editor/spec.md

- Source: openspec/changes/agent-management-ui/specs/prompt-editor/spec.md
- Lines: 1-24
- SHA256: 8c4a7b5f4e0861fb3845fc4680eb30d69da4adbe4c7efff5d2d2b0763f3b5c3b

```md
## ADDED Requirements

### Requirement: CodeMirror 6 Prompt Editor
The system SHALL use CodeMirror 6 as the editor for System Prompt in the Agent Drawer.

#### Scenario: Markdown editing
- **WHEN** user edits the system prompt
- **THEN** CodeMirror 6 editor renders with Markdown syntax highlighting

#### Scenario: Word wrap
- **WHEN** system prompt content exceeds the editor width
- **THEN** lines wrap automatically (wordWrap enabled)

#### Scenario: Copy content
- **WHEN** user clicks a copy button near the editor
- **THEN** the full editor content is copied to clipboard as plain text

#### Scenario: Fullscreen toggle
- **WHEN** user clicks the fullscreen button
- **THEN** the editor expands to fill the viewport and a close button appears

#### Scenario: Tab key handling
- **WHEN** user presses Tab in the editor
- **THEN** 2 spaces are inserted (not navigating focus away)
```

## openspec/changes/agent-management-ui/specs/sidebar-navigation/spec.md

- Source: openspec/changes/agent-management-ui/specs/sidebar-navigation/spec.md
- Lines: 1-31
- SHA256: b19c1af3f439c0b61632ca2a409b9cf7ed93770069a1eb4c26e39626b353df21

```md
## ADDED Requirements

### Requirement: ChatGPT-Style Sidebar
The sidebar SHALL feature a ChatGPT-style layout with a fixed top navigation section and a scrollable Recent Chats section below.

#### Scenario: Top navigation fixed
- **WHEN** the user scrolls the Recent Chats list
- **THEN** the top navigation (AI Studio / New Chat / Agents menu items) remains fixed in place

#### Scenario: Recent Chats scrollable
- **WHEN** there are more chats than fit the available height
- **THEN** only the Recent Chats section scrolls, grouped by Today / Yesterday

#### Scenario: Chat time grouping
- **WHEN** chats are displayed in Recent Chats
- **THEN** they are grouped under "Today" and "Yesterday" headers based on their creation time

### Requirement: Navigation Menu Items
The sidebar navigation SHALL include these menu items: AI Studio (brand), New Chat, Agents, with reserved slots for Tools, Knowledge, MCP, Settings.

#### Scenario: Default menu structure
- **WHEN** the sidebar renders
- **THEN** it displays: AI Studio (brand header), New Chat button, Agents link, future-slot labels (Tools, Knowledge, MCP, Settings) with disabled/locked styling

#### Scenario: Navigate to Agents page
- **WHEN** the user clicks "Agents" in the sidebar
- **THEN** the app navigates to `/agents` route

#### Scenario: Navigate to New Chat
- **WHEN** the user clicks "New Chat" in the sidebar
- **THEN** a new conversation is created and the app navigates to `/`
```

