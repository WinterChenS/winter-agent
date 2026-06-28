---
comet_change: agent-management-ui
role: technical-design
canonical_spec: openspec
---

# Agent Management UI — 技术设计文档

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  App.tsx (Routes)                                           │
│  / → ChatInterface (新 Sidebar + ChatContainer + AgentStatus)│
│  /chat/:id → ChatInterface                                  │
│  /agents → AgentManagement (Card 布局 + Drawer)              │
│  /login → LoginPage                                         │
└─────────────────────────────────────────────────────────────┘
```

三个模块独立组件，通过 Zustand store 和 fetch API 通信。

## 2. Sidebar 组件

### 数据源
- 导航菜单：静态配置
- Recent Chats：后端 `GET /api/chat/history` API

### 布局
```
┌──────────────────┐
│ ✨ AI Studio     │ ← sticky top-0, bg-gray-900
│ 💬 New Chat      │
│ 🤖 Agents        │
│ 🧰 Tools (预留)   │
│ 📚 Knowledge (预留)│
│ 🔌 MCP (预留)     │
│ ⚙ Settings (预留) │
├──────────────────┤
│ Recent Chats     │
│ Today            │ ← 仅此区域 overflow-y-auto
│   聊天1           │
│   聊天2           │
│ Yesterday        │
│   聊天3           │
│   聊天4           │
└──────────────────┘
```

### Session 分组
- `useMemo` 按 `createdAt` 分组到 Today/Yesterday
- 废弃现有 `useSessions` localStorage hook

## 3. Agent 管理页面

### 数据流
```
AgentManagement → useAgent hook → agent.ts API service → fetch /api/agents
                                                              ↓
                                                         AgentCard[]
                                                              ↓
                                                      搜索/排序/分页 (useMemo)
                                                              ↓
                                                      点击 Edit → AgentDrawer
```

### useAgent composable
```typescript
function useAgent() {
  // agents: AgentResponse[]
  // loading: boolean
  // error: string | null
  // fetchAgents, createAgent, updateAgent, deleteAgent,
  // toggleEnable, cloneAgent
}
```

### AgentDrawer 结构
- `position: fixed; right: 0; top: 0; height: 100vh` + `translate-x` + `transition-transform duration-300`
- 遮罩：`bg-black/50` 点击关闭
- 宽度：`w-[480px]` 或 `max-w-md`

## 4. Prompt Editor (CodeMirror 6)

### 依赖
```json
{
  "@codemirror/view": "^6.x",
  "@codemirror/state": "^6.x",
  "@codemirror/lang-markdown": "^6.x",
  "@codemirror/commands": "^6.x"
}
```

### 功能
- Markdown syntax highlighting
- `EditorView.lineWrapping` = true
- 复制按钮 → `navigator.clipboard.writeText(view.state.doc.toString())`
- 全屏按钮 → `position: fixed; inset: 0; z-50`

## 5. Agent 状态展示

### Zustand Store 扩展
已有字段 `activeAgent`, `agentStatus` ('idle' | 'thinking' | 'calling_tool' | 'generating') 已由 `chatApi.ts` SSE handler 更新。只需 UI 渲染：

```tsx
// Chat Header 中
{agentStatus !== 'idle' && activeAgent && (
  <div className="flex items-center gap-2 text-sm text-gray-400">
    <span>{activeAgent.icon}</span>
    <span>{activeAgent.displayName}</span>
    <span>{statusLabel[agentStatus]}</span>
  </div>
)}
```

## 6. 测试策略

| 类型 | 工具 | 覆盖 |
|------|------|------|
| hook 逻辑 | vitest + @testing-library/react-hooks | useAgent CRUD |
| 组件渲染 | vitest + @testing-library/react | Sidebar, AgentCard, AgentDrawer |
| 集成 | vitest | API service fetch mock |
