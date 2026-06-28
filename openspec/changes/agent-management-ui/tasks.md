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
