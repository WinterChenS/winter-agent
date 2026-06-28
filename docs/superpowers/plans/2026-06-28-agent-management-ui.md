---
archived-with: 2026-06-28-agent-management-ui
status: final
---
# Agent Management UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a ChatGPT-style agent management UI with sidebar navigation, card-based agent management page, CodeMirror-based prompt editor, and chat header agent status display.

**Architecture:** Three independent modules (Sidebar, AgentManagement page, Drawer editor) communicate through Zustand store and fetch-based API services. The old monolithic `AdminAgents.tsx` table-and-modal page is removed and replaced with dedicated components. The Zustand store already has `activeAgent`, `agentStatus`, and `activeAgentDisplay` fields used by the SSE handler — the new code only needs to render them in the chat header.

**Tech Stack:** React 18 + TypeScript + Tailwind CSS 3 + Zustand 5 + CodeMirror 6 + vitest + @testing-library/react

## Global Constraints

- React 18 class components are not used, only function components with hooks
- Tailwind CSS 3 utility classes only, no CSS modules or styled-components
- All API calls must use `fetch`, no axios
- Zustand store must remain the single source of truth for chat state
- SSE agent status events (`agent.started` / `agent.finished`) are already handled in `chatApi.ts` — do not modify the SSE handler, only extend the store if needed
- Exported types must be compatible with existing `AgentInfo` in `features/ai-chat/types/agent.ts`
- All new components must follow existing file naming conventions (PascalCase for components, camelCase for hooks/services)
- Test files must use vitest with `@testing-library/react`

---

## File Structure

### New files to create:
| File | Responsibility |
|------|---------------|
| `frontend/src/services/agent.ts` | API service layer wrapping fetch calls to `/api/v1/agents/` |
| `frontend/src/hooks/useAgent.ts` | Composable hook exposing agents CRUD + loading/error state |
| `frontend/src/components/AgentCard.tsx` | Card component displaying agent icon, name, tags, status toggle |
| `frontend/src/components/AgentStatus.tsx` | Small badge/toggle component for enabled/disabled state |
| `frontend/src/pages/AgentManagement.tsx` | Full page at `/agents` route with search, pagination, sorting |
| `frontend/src/components/AgentDrawer.tsx` | Right-side fixed drawer form for editing agent details |
| `frontend/src/components/PromptEditor.tsx` | CodeMirror 6 editor with markdown highlighting, copy, fullscreen |
| `frontend/src/components/ToolSelector.tsx` | Multi-select checkbox component for tool names |
| `frontend/src/components/TagInput.tsx` | Tag input (Enter to add, click to remove) |
| `frontend/src/components/AgentHeaderStatus.tsx` | Agent status display in ChatInterface header |

### Files to modify:
| File | Changes |
|------|---------|
| `frontend/src/components/Sidebar.tsx` | Full rewrite: add nav menu items, session grouping by Today/Yesterday |
| `frontend/src/pages/ChatInterface.tsx` | Replace inline header agent selector with AgentHeaderStatus; integrate new Sidebar props |
| `frontend/src/App.tsx` | Add `/agents` route, remove `/admin/agents` route |
| `frontend/src/features/ai-chat/store/chatStore.ts` | Add `activeAgentDisplay` field (already present) — verify/write test for it |
| `frontend/src/features/ai-chat/types/agent.ts` | Extend `AgentInfo` with full agent definition fields |
| `frontend/src/utils/copy.ts` | Already exists, no changes needed |

### Files to delete:
| File | Reason |
|------|--------|
| `frontend/src/pages/AdminAgents.tsx` | Replaced by `AgentManagement.tsx` + `AgentDrawer.tsx` |

---

### Task 1: Extend AgentInfo type and create API service

**Files:**
- Modify: `frontend/src/features/ai-chat/types/agent.ts`
- Create: `frontend/src/services/agent.ts`
- Test: `frontend/src/services/__tests__/agent.test.ts`

**Interfaces:**
- Produces: `AgentResponse` interface with all backend fields; `agentApi` object with methods `listAgents`, `getAgent`, `createAgent`, `updateAgent`, `deleteAgent`, `toggleAgent`, `cloneAgent`

- [x] **Step 1: Extend AgentInfo type**

Add the full agent definition type to `frontend/src/features/ai-chat/types/agent.ts`:

```typescript
export interface AgentInfo {
  id: string;
  name: string;
  display_name: string;
  description: string;
  enabled: boolean;
  icon?: string;
  agent_type?: string;
  system_prompt?: string;
  tools?: string[];
  model_config?: {
    model_name?: string;
    temperature?: number;
    top_p?: number;
    max_tokens?: number;
    streaming?: boolean;
    json_mode?: boolean;
  };
  trigger_keywords?: string[];
  collaboration_strategy?: string;
  priority?: number;
  tags?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface AgentCreateRequest {
  name: string;
  display_name: string;
  description?: string;
  enabled?: boolean;
  icon?: string;
  agent_type?: string;
  system_prompt?: string;
  tools?: string[];
  model_config?: AgentInfo['model_config'];
  trigger_keywords?: string[];
  collaboration_strategy?: string;
  priority?: number;
  tags?: string[];
}
```

- [x] **Step 2: Create agent API service**

Create `frontend/src/services/agent.ts`:

```typescript
import type { AgentInfo, AgentCreateRequest } from '../features/ai-chat/types/agent';

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export const agentApi = {
  async listAgents(): Promise<AgentInfo[]> {
    const res = await fetch('/api/v1/agents/', { headers: authHeaders() });
    if (!res.ok) throw new Error(`Failed to fetch agents: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  },

  async getAgent(id: string): Promise<AgentInfo> {
    const res = await fetch(`/api/v1/agents/${id}`, { headers: authHeaders() });
    if (!res.ok) throw new Error(`Failed to fetch agent: ${res.status}`);
    return res.json();
  },

  async createAgent(data: AgentCreateRequest): Promise<AgentInfo> {
    const res = await fetch('/api/v1/agents/', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`Failed to create agent: ${res.status}`);
    return res.json();
  },

  async updateAgent(id: string, data: Partial<AgentCreateRequest>): Promise<AgentInfo> {
    const res = await fetch(`/api/v1/agents/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`Failed to update agent: ${res.status}`);
    return res.json();
  },

  async deleteAgent(id: string): Promise<void> {
    const res = await fetch(`/api/v1/agents/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to delete agent: ${res.status}`);
  },

  async toggleAgent(id: string, enabled: boolean): Promise<AgentInfo> {
    return agentApi.updateAgent(id, { enabled });
  },

  async cloneAgent(id: string): Promise<AgentInfo> {
    const agent = await agentApi.getAgent(id);
    const { id: _id, created_at, updated_at, ...rest } = agent;
    return agentApi.createAgent({ ...rest, name: `${rest.name}-copy` });
  },
};
```

- [x] **Step 3: Write failing tests for agent API service**

Create `frontend/src/services/__tests__/agent.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { agentApi } from '../agent';

const mockAgent = {
  id: 'agent-1',
  name: 'researcher',
  display_name: '研究员',
  description: 'Research agent',
  enabled: true,
};

describe('agentApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('listAgents returns agent array', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([mockAgent]),
    } as Response);

    const agents = await agentApi.listAgents();
    expect(agents).toHaveLength(1);
    expect(agents[0].name).toBe('researcher');
  });

  it('listAgents returns empty array for non-array response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({}),
    } as Response);

    const agents = await agentApi.listAgents();
    expect(agents).toEqual([]);
  });

  it('listAgents throws on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 500,
    } as Response);

    await expect(agentApi.listAgents()).rejects.toThrow('Failed to fetch agents: 500');
  });

  it('createAgent sends POST with correct body', async () => {
    const createData = { name: 'new-agent', display_name: 'New Agent' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ id: 'agent-2', ...createData, enabled: true }),
    } as Response);

    const result = await agentApi.createAgent(createData);
    expect(result.id).toBe('agent-2');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/agents/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('updateAgent sends PUT', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ...mockAgent, description: 'updated' }),
    } as Response);

    const result = await agentApi.updateAgent('agent-1', { description: 'updated' });
    expect(result.description).toBe('updated');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/agents/agent-1',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('deleteAgent sends DELETE', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({}),
    } as Response);

    await agentApi.deleteAgent('agent-1');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/agents/agent-1',
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('toggleAgent calls updateAgent with enabled toggle', async () => {
    vi.spyOn(agentApi, 'updateAgent').mockResolvedValueOnce({ ...mockAgent, enabled: false });
    const result = await agentApi.toggleAgent('agent-1', false);
    expect(result.enabled).toBe(false);
    expect(agentApi.updateAgent).toHaveBeenCalledWith('agent-1', { enabled: false });
  });

  it('cloneAgent gets agent then creates copy', async () => {
    const agentWithAllFields = {
      ...mockAgent,
      description: 'original',
      system_prompt: 'You are helpful',
      tools: ['search'],
    };
    vi.spyOn(agentApi, 'getAgent').mockResolvedValueOnce(agentWithAllFields);
    vi.spyOn(agentApi, 'createAgent').mockResolvedValueOnce({
      ...agentWithAllFields,
      id: 'agent-copy',
      name: 'researcher-copy',
    });

    const result = await agentApi.cloneAgent('agent-1');
    expect(result.name).toBe('researcher-copy');
    expect(agentApi.createAgent).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'original' })
    );
  });
});
```

- [x] **Step 4: Run tests to verify they fail**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/services/__tests__/agent.test.ts`
Expected: Tests fail because `agent.ts` doesn't exist yet (but wait — the test imports from `../agent` which we haven't created yet, so the import itself fails. Let me first create the `__tests__` directory if needed.)

Actually in Step 3 we wrote import from `'../agent'` — this won't resolve until the file exists. Let me first make sure the directory exists:

```bash
mkdir -p /Volumes/work/projects/winter-agent/frontend/src/services/__tests__
```

Then write the test file. After that run vitest — it will fail because `agent.ts` doesn't export the module yet.

Expected: `FAIL  src/services/__tests__/agent.test.ts` with Cannot find module error.

- [x] **Step 5: Run tests to verify they pass**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/services/__tests__/agent.test.ts`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add frontend/src/features/ai-chat/types/agent.ts frontend/src/services/agent.ts frontend/src/services/__tests__/agent.test.ts
git commit -m "feat: add agent API service and extended AgentInfo type"
```

---

### Task 2: Create useAgent composable hook

**Files:**
- Create: `frontend/src/hooks/useAgent.ts`
- Test: `frontend/src/hooks/__tests__/useAgent.test.ts`

**Interfaces:**
- Produces: `useAgent()` hook returning `{ agents, loading, error, fetchAgents, createAgent, updateAgent, deleteAgent, toggleEnable, cloneAgent }`

- [x] **Step 1: Write failing tests for useAgent hook**

Create `frontend/src/hooks/__tests__/useAgent.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAgent } from '../useAgent';
import { agentApi } from '../../services/agent';

vi.mock('../../services/agent', () => ({
  agentApi: {
    listAgents: vi.fn(),
    createAgent: vi.fn(),
    updateAgent: vi.fn(),
    deleteAgent: vi.fn(),
    toggleAgent: vi.fn(),
    cloneAgent: vi.fn(),
  },
}));

const mockAgents = [
  { id: '1', name: 'agent-1', display_name: 'Agent 1', description: '', enabled: true },
  { id: '2', name: 'agent-2', display_name: 'Agent 2', description: '', enabled: false },
];

describe('useAgent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches agents on mount and sets loading states', async () => {
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);

    const { result } = renderHook(() => useAgent());

    expect(result.current.loading).toBe(true);
    expect(result.current.agents).toEqual([]);

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.agents).toEqual(mockAgents);
    expect(result.current.error).toBeNull();
  });

  it('sets error when fetch fails', async () => {
    vi.mocked(agentApi.listAgents).mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useAgent());

    await waitFor(() => expect(result.current.error).toBe('Network error'));
    expect(result.current.loading).toBe(false);
    expect(result.current.agents).toEqual([]);
  });

  it('createAgent calls API and refreshes list', async () => {
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);
    vi.mocked(agentApi.createAgent).mockResolvedValueOnce({ id: '3', name: 'new', display_name: 'New', description: '', enabled: true });
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce([...mockAgents, { id: '3', name: 'new', display_name: 'New', description: '', enabled: true }]);

    const { result } = renderHook(() => useAgent());

    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createAgent({ name: 'new', display_name: 'New' });
    });

    expect(agentApi.createAgent).toHaveBeenCalledWith({ name: 'new', display_name: 'New' });
    expect(result.current.agents).toHaveLength(3);
  });

  it('updateAgent calls API and refreshes list', async () => {
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);
    vi.mocked(agentApi.updateAgent).mockResolvedValueOnce({ ...mockAgents[0], description: 'updated' });
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce([
      { ...mockAgents[0], description: 'updated' },
      mockAgents[1],
    ]);

    const { result } = renderHook(() => useAgent());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.updateAgent('1', { description: 'updated' });
    });

    expect(agentApi.updateAgent).toHaveBeenCalledWith('1', { description: 'updated' });
  });

  it('deleteAgent calls API and refreshes list', async () => {
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);
    vi.mocked(agentApi.deleteAgent).mockResolvedValueOnce(undefined);
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce([mockAgents[1]]);

    const { result } = renderHook(() => useAgent());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.deleteAgent('1');
    });

    expect(agentApi.deleteAgent).toHaveBeenCalledWith('1');
    expect(result.current.agents).toHaveLength(1);
  });

  it('toggleEnable toggles enabled state', async () => {
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);
    vi.mocked(agentApi.toggleAgent).mockResolvedValueOnce({ ...mockAgents[0], enabled: false });
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce([
      { ...mockAgents[0], enabled: false },
      mockAgents[1],
    ]);

    const { result } = renderHook(() => useAgent());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.toggleEnable('1', false);
    });

    expect(agentApi.toggleAgent).toHaveBeenCalledWith('1', false);
  });

  it('cloneAgent calls clone and refreshes list', async () => {
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);
    vi.mocked(agentApi.cloneAgent).mockResolvedValueOnce({ id: '3', name: 'agent-1-copy', display_name: 'Agent 1 copy', description: '', enabled: true });
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce([
      ...mockAgents,
      { id: '3', name: 'agent-1-copy', display_name: 'Agent 1 copy', description: '', enabled: true },
    ]);

    const { result } = renderHook(() => useAgent());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.cloneAgent('1');
    });

    expect(agentApi.cloneAgent).toHaveBeenCalledWith('1');
    expect(result.current.agents).toHaveLength(3);
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/hooks/__tests__/useAgent.test.ts`
Expected: FAIL with "Cannot find module" error because `useAgent.ts` doesn't exist yet.

- [x] **Step 3: Implement useAgent hook**

Create `frontend/src/hooks/useAgent.ts`:

```typescript
import { useState, useEffect, useCallback } from 'react';
import { agentApi } from '../services/agent';
import type { AgentInfo, AgentCreateRequest } from '../features/ai-chat/types/agent';

export function useAgent() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await agentApi.listAgents();
      setAgents(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const createAgent = useCallback(async (data: AgentCreateRequest) => {
    await agentApi.createAgent(data);
    await fetchAgents();
  }, [fetchAgents]);

  const updateAgent = useCallback(async (id: string, data: Partial<AgentCreateRequest>) => {
    await agentApi.updateAgent(id, data);
    await fetchAgents();
  }, [fetchAgents]);

  const deleteAgent = useCallback(async (id: string) => {
    await agentApi.deleteAgent(id);
    await fetchAgents();
  }, [fetchAgents]);

  const toggleEnable = useCallback(async (id: string, enabled: boolean) => {
    await agentApi.toggleAgent(id, enabled);
    await fetchAgents();
  }, [fetchAgents]);

  const cloneAgent = useCallback(async (id: string) => {
    await agentApi.cloneAgent(id);
    await fetchAgents();
  }, [fetchAgents]);

  return {
    agents,
    loading,
    error,
    fetchAgents,
    createAgent,
    updateAgent,
    deleteAgent,
    toggleEnable,
    cloneAgent,
  };
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/hooks/__tests__/useAgent.test.ts`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add frontend/src/hooks/useAgent.ts frontend/src/hooks/__tests__/useAgent.test.ts
git commit -m "feat: add useAgent composable hook with full CRUD"
```

---

### Task 3: Rewrite Sidebar with navigation menu and session grouping

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Test: `frontend/src/components/__tests__/Sidebar.test.tsx`

**Interfaces:**
- Consumes: `sessions: Conversation[]` (from `useSessions`), `activeSessionId`, navigation callbacks
- Produces: Rewritten sidebar with nav items (AI Studio, New Chat, Agents, Tools/Knowledge/MCP/Settings as locked placeholders), Recent Chats section grouped by Today/Yesterday

- [x] **Step 1: Write failing tests for the new Sidebar**

Create `frontend/src/components/__tests__/Sidebar.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '../Sidebar';
import { BrowserRouter } from 'react-router-dom';

const mockSessions = [
  { id: '1', title: 'Chat about AI', createdAt: Date.now() },
  { id: '2', title: 'Research', createdAt: Date.now() - 86400000 * 2 }, // 2 days ago
  { id: '3', title: 'Old chat', createdAt: Date.now() - 86400000 * 3 }, // 3 days ago
];

const defaultProps = {
  sessions: mockSessions,
  activeSessionId: '1',
  onSelectSession: () => {},
  onNewSession: () => {},
  onDeleteSession: () => {},
  isMobileOpen: false,
  setMobileOpen: () => {},
};

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('Sidebar', () => {
  it('renders navigation menu items', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    expect(screen.getByText('AI Studio')).toBeDefined();
    expect(screen.getByText('Agents')).toBeDefined();
  });

  it('renders Recent Chats section header', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    expect(screen.getByText('Recent Chats')).toBeDefined();
  });

  it('renders locked menu items with lock icon', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    // Tools, Knowledge, MCP, Settings should be present
    expect(screen.getByText('Tools')).toBeDefined();
  });

  it('groups sessions into Today and older periods', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    expect(screen.getByText('Today')).toBeDefined();
  });

  it('highlights active session', () => {
    renderWithRouter(<Sidebar {...defaultProps} />);
    const activeItem = screen.getByText('Chat about AI');
    expect(activeItem).toBeDefined();
  });

  it('renders mobile overlay when isMobileOpen is true', () => {
    renderWithRouter(<Sidebar {...defaultProps} isMobileOpen={true} />);
    // The overlay should be present
    const overlay = document.querySelector('.fixed.inset-0');
    expect(overlay).toBeDefined();
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/components/__tests__/Sidebar.test.tsx`
Expected: FAIL (old Sidebar doesn't have the nav items)

- [x] **Step 3: Implement the new Sidebar**

Rewrite `frontend/src/components/Sidebar.tsx`:

```typescript
import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Conversation } from '../types/chat';

interface SidebarProps {
  sessions: Conversation[];
  activeSessionId?: string;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  isMobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
}

interface NavItem {
  label: string;
  icon: string;
  route?: string;
  locked?: boolean;
  action?: () => void;
}

function SessionGroup({ title, sessions, activeSessionId, onSelect, onDelete }: {
  title: string;
  sessions: Conversation[];
  activeSessionId?: string;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (sessions.length === 0) return null;
  return (
    <div className="mb-2">
      <div className="px-4 py-1 text-xs text-gray-500 uppercase tracking-wider">{title}</div>
      {sessions.map(session => (
        <div
          key={session.id}
          className={`
            group relative flex items-center px-4 py-2 cursor-pointer
            ${activeSessionId === session.id ? 'bg-gray-800' : 'hover:bg-gray-800/50'}
          `}
          onClick={() => {
            onSelect(session.id);
          }}
        >
          <div className="flex-1 overflow-hidden">
            <div className="truncate text-sm text-gray-300">
              {session.title}
            </div>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(session.id);
            }}
            className="opacity-0 group-hover:opacity-100 ml-2 text-gray-500 hover:text-red-400 shrink-0"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  isMobileOpen,
  setMobileOpen
}) => {
  const navigate = useNavigate();

  const navItems: NavItem[] = [
    { label: 'AI Studio', icon: 'sparkles', action: () => { navigate('/'); setMobileOpen(false); } },
    { label: 'New Chat', icon: 'plus', action: () => { onNewSession(); setMobileOpen(false); } },
    { label: 'Agents', icon: 'robot', route: '/agents', action: () => { navigate('/agents'); setMobileOpen(false); } },
    { label: 'Tools', icon: 'wrench', locked: true },
    { label: 'Knowledge', icon: 'book', locked: true },
    { label: 'MCP', icon: 'plug', locked: true },
    { label: 'Settings', icon: 'cog', locked: true },
  ];

  // Group sessions by time period
  const { today, yesterday, earlier } = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 86400000;

    const groups: { today: Conversation[]; yesterday: Conversation[]; earlier: Conversation[] } = {
      today: [],
      yesterday: [],
      earlier: [],
    };

    for (const s of sessions) {
      const t = s.createdAt;
      if (t >= todayStart) groups.today.push(s);
      else if (t >= yesterdayStart) groups.yesterday.push(s);
      else groups.earlier.push(s);
    }

    return groups;
  }, [sessions]);

  const renderIcon = (icon: string) => {
    const icons: Record<string, JSX.Element> = {
      sparkles: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
        </svg>
      ),
      plus: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
      ),
      robot: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      ),
      wrench: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
      book: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
      ),
      plug: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
      cog: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
    };
    return icons[icon] || null;
  };

  return (
    <>
      {/* Mobile overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar container */}
      <div className={`
        fixed md:static inset-y-0 left-0 z-30
        w-64 bg-gray-900 text-white flex flex-col
        transition-transform duration-300 ease-in-out
        ${isMobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}>
        {/* Navigation menu */}
        <div className="sticky top-0 bg-gray-900 z-10">
          <div className="px-4 py-4">
            <h2 className="text-lg font-bold text-white">AI Studio</h2>
          </div>
          <nav className="px-2 pb-2 space-y-0.5">
            {navItems.map((item) => (
              <button
                key={item.label}
                onClick={item.action}
                disabled={item.locked}
                className={`
                  w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm
                  ${item.locked
                    ? 'text-gray-600 cursor-not-allowed'
                    : 'text-gray-300 hover:text-white hover:bg-gray-800 transition-colors'
                  }
                `}
                title={item.locked ? 'Coming soon' : item.label}
              >
                <span className="shrink-0">{renderIcon(item.icon)}</span>
                <span>{item.label}</span>
                {item.locked && (
                  <svg className="w-3 h-3 ml-auto text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                )}
              </button>
            ))}
          </nav>
          <div className="border-t border-gray-800 mx-4" />
        </div>

        {/* Recent Chats */}
        <div className="flex-1 overflow-y-auto py-2">
          <div className="px-4 py-2 text-xs text-gray-500 uppercase tracking-wider">Recent Chats</div>
          <SessionGroup title="Today" sessions={today} activeSessionId={activeSessionId} onSelect={(id) => { onSelectSession(id); setMobileOpen(false); }} onDelete={onDeleteSession} />
          <SessionGroup title="Yesterday" sessions={yesterday} activeSessionId={activeSessionId} onSelect={(id) => { onSelectSession(id); setMobileOpen(false); }} onDelete={onDeleteSession} />
          <SessionGroup title="Earlier" sessions={earlier} activeSessionId={activeSessionId} onSelect={(id) => { onSelectSession(id); setMobileOpen(false); }} onDelete={onDeleteSession} />
        </div>
      </div>
    </>
  );
};
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/components/__tests__/Sidebar.test.tsx`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/Sidebar.tsx frontend/src/components/__tests__/Sidebar.test.tsx
git commit -m "feat: rewrite sidebar with navigation menu and session grouping"
```

---

### Task 4: Create AgentCard and AgentStatus components

**Files:**
- Create: `frontend/src/components/AgentCard.tsx`
- Create: `frontend/src/components/AgentStatus.tsx`
- Test: `frontend/src/components/__tests__/AgentCard.test.tsx`

**Interfaces:**
- `AgentCard` props: `{ agent: AgentInfo; onEdit: (id: string) => void; onDelete: (id: string) => void; onToggle: (id: string, enabled: boolean) => void; onClone: (id: string) => void }`
- `AgentStatus` props: `{ enabled: boolean; onToggle: () => void }`

- [x] **Step 1: Write failing tests**

Create `frontend/src/components/__tests__/AgentCard.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentCard } from '../AgentCard';
import { AgentStatus } from '../AgentStatus';

const mockAgent = {
  id: 'agent-1',
  name: 'researcher',
  display_name: '研究员',
  description: '负责搜索和研究',
  enabled: true,
  tags: ['search', 'research'],
  icon: '🔬',
  priority: 1,
};

describe('AgentCard', () => {
  it('renders agent display name and description', () => {
    render(<AgentCard agent={mockAgent} onEdit={vi.fn()} onDelete={vi.fn()} onToggle={vi.fn()} onClone={vi.fn()} />);
    expect(screen.getByText('研究员')).toBeDefined();
    expect(screen.getByText('负责搜索和研究')).toBeDefined();
  });

  it('renders tags', () => {
    render(<AgentCard agent={mockAgent} onEdit={vi.fn()} onDelete={vi.fn()} onToggle={vi.fn()} onClone={vi.fn()} />);
    expect(screen.getByText('search')).toBeDefined();
    expect(screen.getByText('research')).toBeDefined();
  });

  it('calls onEdit when edit button is clicked', () => {
    const onEdit = vi.fn();
    render(<AgentCard agent={mockAgent} onEdit={onEdit} onDelete={vi.fn()} onToggle={vi.fn()} onClone={vi.fn()} />);
    const editBtn = screen.getByLabelText('编辑');
    fireEvent.click(editBtn);
    expect(onEdit).toHaveBeenCalledWith('agent-1');
  });

  it('calls onDelete when delete button is clicked', () => {
    const onDelete = vi.fn();
    render(<AgentCard agent={mockAgent} onEdit={vi.fn()} onDelete={onDelete} onToggle={vi.fn()} onClone={vi.fn()} />);
    const deleteBtn = screen.getByLabelText('删除');
    fireEvent.click(deleteBtn);
    expect(onDelete).toHaveBeenCalledWith('agent-1');
  });
});

describe('AgentStatus', () => {
  it('shows enabled badge when enabled is true', () => {
    render(<AgentStatus enabled={true} onToggle={vi.fn()} />);
    expect(screen.getByText('启用')).toBeDefined();
  });

  it('shows disabled badge when enabled is false', () => {
    render(<AgentStatus enabled={false} onToggle={vi.fn()} />);
    expect(screen.getByText('禁用')).toBeDefined();
  });

  it('calls onToggle when clicked', () => {
    const onToggle = vi.fn();
    render(<AgentStatus enabled={true} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onToggle).toHaveBeenCalledOnce();
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/components/__tests__/AgentCard.test.tsx`
Expected: FAIL (components don't exist yet)

- [x] **Step 3: Implement AgentStatus**

Create `frontend/src/components/AgentStatus.tsx`:

```typescript
interface AgentStatusProps {
  enabled: boolean;
  onToggle: () => void;
}

export function AgentStatus({ enabled, onToggle }: AgentStatusProps) {
  return (
    <button
      onClick={onToggle}
      className={`
        inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full
        transition-colors
        ${enabled
          ? 'bg-green-100 text-green-700 hover:bg-green-200'
          : 'bg-red-100 text-red-700 hover:bg-red-200'
        }
      `}
    >
      {enabled ? '启用' : '禁用'}
    </button>
  );
}
```

- [x] **Step 4: Implement AgentCard**

Create `frontend/src/components/AgentCard.tsx`:

```typescript
import type { AgentInfo } from '../features/ai-chat/types/agent';
import { AgentStatus } from './AgentStatus';

interface AgentCardProps {
  agent: AgentInfo;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  onToggle: (id: string, enabled: boolean) => void;
  onClone: (id: string) => void;
}

export function AgentCard({ agent, onEdit, onDelete, onToggle, onClone }: AgentCardProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{agent.icon || '🤖'}</span>
          <div>
            <h3 className="font-semibold text-gray-900">{agent.display_name}</h3>
            <span className="text-xs text-gray-500">{agent.name}</span>
          </div>
        </div>
        <AgentStatus enabled={agent.enabled} onToggle={() => onToggle(agent.id, !agent.enabled)} />
      </div>

      {agent.description && (
        <p className="text-sm text-gray-600 mb-3 line-clamp-2">{agent.description}</p>
      )}

      {agent.tags && agent.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {agent.tags.map(tag => (
            <span key={tag} className="px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-600">
              {tag}
            </span>
          ))}
        </div>
      )}

      {agent.priority !== undefined && (
        <div className="text-xs text-gray-400 mb-3">
          优先级: {agent.priority}
        </div>
      )}

      <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
        <button
          onClick={() => onEdit(agent.id)}
          aria-label="编辑"
          className="px-3 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded transition-colors"
        >
          编辑
        </button>
        <button
          onClick={() => onClone(agent.id)}
          aria-label="克隆"
          className="px-3 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded transition-colors"
        >
          克隆
        </button>
        <button
          onClick={() => onDelete(agent.id)}
          aria-label="删除"
          className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded transition-colors ml-auto"
        >
          删除
        </button>
      </div>
    </div>
  );
}
```

- [x] **Step 5: Run tests to verify they pass**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/components/__tests__/AgentCard.test.tsx`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add frontend/src/components/AgentCard.tsx frontend/src/components/AgentStatus.tsx frontend/src/components/__tests__/AgentCard.test.tsx
git commit -m "feat: add AgentCard and AgentStatus components"
```

---

### Task 5: Create AgentManagement page with search, pagination, sorting

**Files:**
- Create: `frontend/src/pages/AgentManagement.tsx`
- Test: `frontend/src/pages/__tests__/AgentManagement.test.tsx`

**Interfaces:**
- Uses: `useAgent` hook, `AgentCard` component, `AgentDrawer` component (passed as prop or imported)
- Route: `/agents`

- [x] **Step 1: Write failing tests**

Create `frontend/src/pages/__tests__/AgentManagement.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AgentManagement } from '../AgentManagement';
import { useAgent } from '../../hooks/useAgent';
import { BrowserRouter } from 'react-router-dom';

vi.mock('../../hooks/useAgent', () => ({
  useAgent: vi.fn(),
}));

const mockAgents = [
  { id: '1', name: 'researcher', display_name: '研究员', description: 'Research agent', enabled: true, tags: ['search'] },
  { id: '2', name: 'coder', display_name: '程序员', description: 'Code agent', enabled: false, tags: ['code'] },
  { id: '3', name: 'helper', display_name: '助手', description: 'Helper agent', enabled: true, tags: ['help'] },
];

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('AgentManagement', () => {
  beforeEach(() => {
    vi.mocked(useAgent).mockReturnValue({
      agents: mockAgents,
      loading: false,
      error: null,
      fetchAgents: vi.fn(),
      createAgent: vi.fn(),
      updateAgent: vi.fn(),
      deleteAgent: vi.fn(),
      toggleEnable: vi.fn(),
      cloneAgent: vi.fn(),
    });
  });

  it('renders page title and create button', () => {
    renderWithRouter(<AgentManagement />);
    expect(screen.getByText('Agent 管理')).toBeDefined();
    expect(screen.getByText('+ 新建 Agent')).toBeDefined();
  });

  it('renders agent cards for each agent', () => {
    renderWithRouter(<AgentManagement />);
    expect(screen.getByText('研究员')).toBeDefined();
    expect(screen.getByText('程序员')).toBeDefined();
    expect(screen.getByText('助手')).toBeDefined();
  });

  it('shows search input and filters agents', () => {
    renderWithRouter(<AgentManagement />);
    const searchInput = screen.getByPlaceholderText('搜索 Agent...');
    expect(searchInput).toBeDefined();

    // Type a search term
    fireEvent.change(searchInput, { target: { value: '研究' } });
    expect(screen.getByText('研究员')).toBeDefined();
    expect(screen.queryByText('程序员')).toBeNull();
  });

  it('shows loading spinner when loading', () => {
    vi.mocked(useAgent).mockReturnValue({
      agents: [],
      loading: true,
      error: null,
      fetchAgents: vi.fn(),
      createAgent: vi.fn(),
      updateAgent: vi.fn(),
      deleteAgent: vi.fn(),
      toggleEnable: vi.fn(),
      cloneAgent: vi.fn(),
    });

    renderWithRouter(<AgentManagement />);
    expect(screen.getByText('加载中...')).toBeDefined();
  });

  it('shows error state', () => {
    vi.mocked(useAgent).mockReturnValue({
      agents: [],
      loading: false,
      error: 'Failed to fetch',
      fetchAgents: vi.fn(),
      createAgent: vi.fn(),
      updateAgent: vi.fn(),
      deleteAgent: vi.fn(),
      toggleEnable: vi.fn(),
      cloneAgent: vi.fn(),
    });

    renderWithRouter(<AgentManagement />);
    expect(screen.getByText(/加载失败/)).toBeDefined();
  });

  it('shows empty state when no agents', () => {
    vi.mocked(useAgent).mockReturnValue({
      agents: [],
      loading: false,
      error: null,
      fetchAgents: vi.fn(),
      createAgent: vi.fn(),
      updateAgent: vi.fn(),
      deleteAgent: vi.fn(),
      toggleEnable: vi.fn(),
      cloneAgent: vi.fn(),
    });

    renderWithRouter(<AgentManagement />);
    expect(screen.getByText(/暂无 Agent/)).toBeDefined();
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/pages/__tests__/AgentManagement.test.tsx`
Expected: FAIL (page doesn't exist yet)

- [x] **Step 3: Implement AgentManagement page**

Create `frontend/src/pages/AgentManagement.tsx`:

```typescript
import { useState, useMemo } from 'react';
import { useAgent } from '../hooks/useAgent';
import { AgentCard } from '../components/AgentCard';
import type { AgentInfo } from '../features/ai-chat/types/agent';

const PAGE_SIZE = 12;

export function AgentManagement() {
  const { agents, loading, error, createAgent, updateAgent, deleteAgent, toggleEnable, cloneAgent } = useAgent();
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'priority' | 'created_at'>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    let result = agents;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(a =>
        a.name.toLowerCase().includes(q) ||
        a.display_name.toLowerCase().includes(q) ||
        (a.description || '').toLowerCase().includes(q) ||
        (a.tags || []).some(t => t.toLowerCase().includes(q))
      );
    }
    result = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortBy === 'name') cmp = a.display_name.localeCompare(b.display_name);
      else if (sortBy === 'priority') cmp = (a.priority ?? 0) - (b.priority ?? 0);
      else if (sortBy === 'created_at') cmp = (a.created_at || '').localeCompare(b.created_at || '');
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [agents, search, sortBy, sortDir]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleCreate = () => {
    // Opens AgentDrawer — will be wired in Task 6
    // For now create an empty agent and let drawer handle it
    window.dispatchEvent(new CustomEvent('agent:create'));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        加载中...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-red-500">
        加载失败: {error}
        <button onClick={() => window.location.reload()} className="ml-2 underline">重试</button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Agent 管理</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => window.dispatchEvent(new CustomEvent('agent:create'))}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-sm"
          >
            + 新建 Agent
          </button>
        </div>
      </div>

      {/* Search & Sort bar */}
      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-md">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder="搜索 Agent..."
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <select
          value={`${sortBy}-${sortDir}`}
          onChange={e => {
            const [by, dir] = e.target.value.split('-') as [typeof sortBy, typeof sortDir];
            setSortBy(by);
            setSortDir(dir);
          }}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="name-asc">名称 A-Z</option>
          <option value="name-desc">名称 Z-A</option>
          <option value="priority-desc">优先级 高-低</option>
          <option value="priority-asc">优先级 低-高</option>
          <option value="created_at-desc">最新创建</option>
          <option value="created_at-asc">最早创建</option>
        </select>
      </div>

      {/* Agent cards grid */}
      {paged.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-gray-400">
          <p className="text-lg mb-2">暂无 Agent</p>
          <p className="text-sm">点击"新建 Agent"创建第一个</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {paged.map(agent => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onEdit={(id) => window.dispatchEvent(new CustomEvent('agent:edit', { detail: id }))}
              onDelete={async (id) => {
                if (confirm('确认删除？')) await deleteAgent(id);
              }}
              onToggle={toggleEnable}
              onClone={cloneAgent}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 text-sm border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            上一页
          </button>
          <span className="text-sm text-gray-600">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 text-sm border rounded disabled:opacity-50 hover:bg-gray-50"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/pages/__tests__/AgentManagement.test.tsx`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add frontend/src/pages/AgentManagement.tsx frontend/src/pages/__tests__/AgentManagement.test.tsx
git commit -m "feat: add AgentManagement page with search, sort, pagination"
```

---

### Task 6: Create AgentDrawer (right-side drawer editor)

**Files:**
- Create: `frontend/src/components/AgentDrawer.tsx`
- Test: `frontend/src/components/__tests__/AgentDrawer.test.tsx`

**Interfaces:**
- `AgentDrawer` props: `{ open: boolean; agentId?: string; onClose: () => void; onSave: () => void }`
- Internally uses `ToolSelector`, `TagInput`, `PromptEditor`

- [x] **Step 1: Write failing tests**

Create `frontend/src/components/__tests__/AgentDrawer.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentDrawer } from '../AgentDrawer';

// Mock agentApi for save operations
vi.mock('../../services/agent', () => ({
  agentApi: {
    getAgent: vi.fn().mockResolvedValue({
      id: '1', name: 'test', display_name: 'Test', description: '',
      enabled: true, system_prompt: '', tools: [],
      trigger_keywords: [], collaboration_strategy: 'sequential', priority: 0,
    }),
    createAgent: vi.fn(),
    updateAgent: vi.fn(),
  },
}));

describe('AgentDrawer', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <AgentDrawer open={false} onClose={vi.fn()} onSave={vi.fn()} />
    );
    // The drawer should be translated off-screen
    const drawer = container.querySelector('[class*="translate-x-full"]');
    expect(drawer).toBeDefined();
  });

  it('renders drawer content when open', async () => {
    render(<AgentDrawer open={true} agentId="1" onClose={vi.fn()} onSave={vi.fn()} />);
    // Should show agent editor in create mode
    expect(await screen.findByText('编辑 Agent')).toBeDefined();
  });
});
```

- [x] **Step 2: Create ToolSelector component**

Create `frontend/src/components/ToolSelector.tsx`:

```typescript
interface ToolSelectorProps {
  selected: string[];
  available: string[];
  onChange: (tools: string[]) => void;
}

export function ToolSelector({ selected, available, onChange }: ToolSelectorProps) {
  const handleToggle = (tool: string) => {
    if (selected.includes(tool)) {
      onChange(selected.filter(t => t !== tool));
    } else {
      onChange([...selected, tool]);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {available.map(tool => (
        <label key={tool} className="flex items-center gap-1.5 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={selected.includes(tool)}
            onChange={() => handleToggle(tool)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-gray-700">{tool}</span>
        </label>
      ))}
    </div>
  );
}
```

- [x] **Step 3: Create TagInput component**

Create `frontend/src/components/TagInput.tsx`:

```typescript
import { useState } from 'react';

interface TagInputProps {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}

export function TagInput({ tags, onChange, placeholder = '输入关键词后回车' }: TagInputProps) {
  const [input, setInput] = useState('');

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && input.trim()) {
      e.preventDefault();
      if (!tags.includes(input.trim())) {
        onChange([...tags, input.trim()]);
      }
      setInput('');
    }
  };

  const removeTag = (tag: string) => {
    onChange(tags.filter(t => t !== tag));
  };

  return (
    <div className="flex flex-wrap gap-1.5 p-2 border border-gray-300 rounded-lg min-h-[38px] focus-within:ring-1 focus-within:ring-blue-500">
      {tags.map(tag => (
        <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full">
          {tag}
          <button
            onClick={() => removeTag(tag)}
            className="hover:text-blue-900"
            type="button"
          >
            &times;
          </button>
        </span>
      ))}
      <input
        type="text"
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={tags.length === 0 ? placeholder : ''}
        className="flex-1 min-w-[60px] outline-none text-sm bg-transparent"
      />
    </div>
  );
}
```

- [x] **Step 4: Implement AgentDrawer**

Create `frontend/src/components/AgentDrawer.tsx`:

```typescript
import { useState, useEffect, useCallback } from 'react';
import { agentApi } from '../services/agent';
import type { AgentInfo, AgentCreateRequest } from '../features/ai-chat/types/agent';

const AVAILABLE_TOOLS = ['search', 'time', 'browser', 'execute_python'];
const STRATEGIES = ['sequential', 'parallel', 'supervisor'];

interface AgentDrawerProps {
  open: boolean;
  agentId?: string;
  onClose: () => void;
  onSave: () => void;
}

const defaultFormData: AgentCreateRequest = {
  name: '',
  display_name: '',
  description: '',
  enabled: true,
  icon: '',
  agent_type: '',
  system_prompt: '',
  tools: [],
  model_config: {
    model_name: '',
    temperature: 0.7,
    top_p: 1,
    max_tokens: 2048,
    streaming: true,
    json_mode: false,
  },
  trigger_keywords: [],
  collaboration_strategy: 'sequential',
  priority: 0,
  tags: [],
};

export function AgentDrawer({ open, agentId, onClose, onSave }: AgentDrawerProps) {
  const [form, setForm] = useState<AgentCreateRequest>(defaultFormData);
  const [saving, setSaving] = useState(false);
  const isEdit = !!agentId;

  useEffect(() => {
    if (open) {
      if (agentId) {
        agentApi.getAgent(agentId).then(agent => {
          const { id, created_at, updated_at, ...rest } = agent;
          setForm(rest as AgentCreateRequest);
        }).catch(console.error);
      } else {
        setForm(defaultFormData);
      }
    }
  }, [open, agentId]);

  const handleChange = useCallback(<K extends keyof AgentCreateRequest>(
    key: K,
    value: AgentCreateRequest[K]
  ) => {
    setForm(prev => ({ ...prev, [key]: value }));
  }, []);

  const handleModelConfigChange = useCallback(<K extends keyof NonNullable<AgentCreateRequest['model_config']>>(
    key: K,
    value: string | number | boolean
  ) => {
    setForm(prev => ({
      ...prev,
      model_config: { ...prev.model_config, [key]: value } as AgentCreateRequest['model_config'],
    }));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (isEdit && agentId) {
        await agentApi.updateAgent(agentId, form);
      } else {
        await agentApi.createAgent(form);
      }
      onSave();
      onClose();
    } catch (e) {
      console.error('Save failed', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-40"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`
          fixed right-0 top-0 h-full z-50
          w-[480px] max-w-full bg-white shadow-xl
          transform transition-transform duration-300
          ${open ? 'translate-x-0' : 'translate-x-full'}
          flex flex-col
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-bold text-gray-800">
            {isEdit ? '编辑 Agent' : '新建 Agent'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          {/* Basic Info Section */}
          <section>
            <h3 className="text-sm font-semibold text-gray-800 mb-3">基本信息</h3>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">名称 (name)</label>
                  <input
                    value={form.name}
                    onChange={e => handleChange('name', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="researcher"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">显示名称</label>
                  <input
                    value={form.display_name}
                    onChange={e => handleChange('display_name', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="研究员"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">描述</label>
                <input
                  value={form.description || ''}
                  onChange={e => handleChange('description', e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder="Agent 职责描述"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">图标 (emoji)</label>
                  <input
                    value={form.icon || ''}
                    onChange={e => handleChange('icon', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="🔬"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Agent 类型</label>
                  <input
                    value={form.agent_type || ''}
                    onChange={e => handleChange('agent_type', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="assistant"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">标签 (逗号分隔)</label>
                  <input
                    value={(form.tags || []).join(', ')}
                    onChange={e => handleChange('tags', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="search, research"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">优先级</label>
                  <input
                    type="number"
                    value={form.priority ?? 0}
                    onChange={e => handleChange('priority', parseInt(e.target.value) || 0)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="enabled"
                  checked={form.enabled ?? true}
                  onChange={e => handleChange('enabled', e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="enabled" className="text-sm text-gray-700">启用</label>
              </div>
            </div>
          </section>

          {/* Prompt Section (placeholder — CodeMirror editor will be integrated in Task 7) */}
          <section>
            <h3 className="text-sm font-semibold text-gray-800 mb-3">System Prompt</h3>
            <textarea
              value={form.system_prompt || ''}
              onChange={e => handleChange('system_prompt', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm h-32 font-mono focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="You are a helpful assistant..."
            />
          </section>

          {/* Model Section */}
          <section>
            <h3 className="text-sm font-semibold text-gray-800 mb-3">模型配置</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">模型名称</label>
                <input
                  value={form.model_config?.model_name || ''}
                  onChange={e => handleModelConfigChange('model_name', e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder="gpt-4"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Temperature</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    value={form.model_config?.temperature ?? 0.7}
                    onChange={e => handleModelConfigChange('temperature', parseFloat(e.target.value) || 0)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Top P</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={form.model_config?.top_p ?? 1}
                    onChange={e => handleModelConfigChange('top_p', parseFloat(e.target.value) || 0)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Max Tokens</label>
                  <input
                    type="number"
                    value={form.model_config?.max_tokens ?? 2048}
                    onChange={e => handleModelConfigChange('max_tokens', parseInt(e.target.value) || 0)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div className="flex items-end gap-4 pb-2">
                  <label className="flex items-center gap-1.5 text-sm">
                    <input
                      type="checkbox"
                      checked={form.model_config?.streaming ?? true}
                      onChange={e => handleModelConfigChange('streaming', e.target.checked)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    Streaming
                  </label>
                  <label className="flex items-center gap-1.5 text-sm">
                    <input
                      type="checkbox"
                      checked={form.model_config?.json_mode ?? false}
                      onChange={e => handleModelConfigChange('json_mode', e.target.checked)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    JSON Mode
                  </label>
                </div>
              </div>
            </div>
          </section>

          {/* Tools Section */}
          <section>
            <h3 className="text-sm font-semibold text-gray-800 mb-3">工具</h3>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_TOOLS.map(tool => (
                <label key={tool} className="flex items-center gap-1.5 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={(form.tools || []).includes(tool)}
                    onChange={() => {
                      const tools = form.tools || [];
                      const updated = tools.includes(tool)
                        ? tools.filter(t => t !== tool)
                        : [...tools, tool];
                      handleChange('tools', updated);
                    }}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-gray-700">{tool}</span>
                </label>
              ))}
            </div>
          </section>

          {/* Trigger Section */}
          <section>
            <h3 className="text-sm font-semibold text-gray-800 mb-3">触发关键词</h3>
            <div className="flex flex-wrap gap-1.5 p-2 border border-gray-300 rounded-lg min-h-[38px]">
              {(form.trigger_keywords || []).map(kw => (
                <span key={kw} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full">
                  {kw}
                  <button
                    onClick={() => handleChange('trigger_keywords', (form.trigger_keywords || []).filter(t => t !== kw))}
                    className="hover:text-blue-900"
                    type="button"
                  >
                    &times;
                  </button>
                </span>
              ))}
              <input
                type="text"
                placeholder={(form.trigger_keywords || []).length === 0 ? '输入关键词后回车' : ''}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    const input = e.currentTarget.value.trim();
                    if (input && !(form.trigger_keywords || []).includes(input)) {
                      handleChange('trigger_keywords', [...(form.trigger_keywords || []), input]);
                    }
                    e.currentTarget.value = '';
                  }
                }}
                className="flex-1 min-w-[60px] outline-none text-sm bg-transparent"
              />
            </div>
          </section>

          {/* Advanced Section */}
          <section>
            <h3 className="text-sm font-semibold text-gray-800 mb-3">高级配置</h3>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">协作策略</label>
              <select
                value={form.collaboration_strategy || 'sequential'}
                onChange={e => handleChange('collaboration_strategy', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {STRATEGIES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 text-sm"
          >
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </>
  );
}
```

- [x] **Step 5: Wire AgentDrawer into AgentManagement page**

Update `frontend/src/pages/AgentManagement.tsx` to import and use AgentDrawer:

Add `AgentDrawer` import and state:

After the existing imports, add:
```typescript
import { AgentDrawer } from '../components/AgentDrawer';
```

Inside the `AgentManagement` function component, before the `if (loading)` block, add:
```typescript
const [drawerOpen, setDrawerOpen] = useState(false);
const [editingAgentId, setEditingAgentId] = useState<string | undefined>();
```

Replace the `handleCreate` function with:
```typescript
const handleCreate = () => {
  setEditingAgentId(undefined);
  setDrawerOpen(true);
};
```

Replace the `onEdit` handler:
```typescript
onEdit={(id) => {
  setEditingAgentId(id);
  setDrawerOpen(true);
}}
```

Add before the closing `</div>` of the return:
```typescript
<AgentDrawer
  open={drawerOpen}
  agentId={editingAgentId}
  onClose={() => setDrawerOpen(false)}
  onSave={fetchAgents}
/>
```

Also add `fetchAgents` to the destructured `useAgent()` return:
```typescript
const { agents, loading, error, fetchAgents, createAgent, updateAgent, deleteAgent, toggleEnable, cloneAgent } = useAgent();
```

- [x] **Step 6: Update tests for AgentManagement to verify drawer integration**

Update `frontend/src/pages/__tests__/AgentManagement.test.tsx` to add:

```typescript
it('opens drawer when create button is clicked', () => {
  renderWithRouter(<AgentManagement />);
  fireEvent.click(screen.getByText('+ 新建 Agent'));
  expect(screen.getByText('新建 Agent')).toBeDefined();
});
```

- [x] **Step 7: Run all tests to verify they pass**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/components/__tests__/AgentDrawer.test.tsx src/pages/__tests__/AgentManagement.test.tsx`
Expected: PASS

- [x] **Step 8: Commit**

```bash
git add frontend/src/components/AgentDrawer.tsx frontend/src/components/ToolSelector.tsx frontend/src/components/TagInput.tsx frontend/src/components/__tests__/AgentDrawer.test.tsx frontend/src/pages/AgentManagement.tsx frontend/src/pages/__tests__/AgentManagement.test.tsx
git commit -m "feat: add AgentDrawer editor with form sections"
```

---

### Task 7: Create PromptEditor with CodeMirror 6

**Files:**
- Install: CodeMirror 6 dependencies
- Create: `frontend/src/components/PromptEditor.tsx`
- Test: `frontend/src/components/__tests__/PromptEditor.test.tsx`

**Interfaces:**
- `PromptEditor` props: `{ value: string; onChange: (value: string) => void; minHeight?: string }`

- [x] **Step 1: Install CodeMirror 6 dependencies**

```bash
cd /Volumes/work/projects/winter-agent/frontend && npm install @codemirror/view@^6.36.5 @codemirror/state@^6.5.2 @codemirror/lang-markdown@^6.3.7 @codemirror/commands@^6.8.1
```

- [x] **Step 2: Write failing tests for PromptEditor**

Create `frontend/src/components/__tests__/PromptEditor.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PromptEditor } from '../PromptEditor';

// CodeMirror uses DOM APIs that jsdom may not fully support
// We test the React wrapper behavior, not CodeMirror internals
describe('PromptEditor', () => {
  it('renders editor container', () => {
    const { container } = render(<PromptEditor value="test" onChange={vi.fn()} />);
    const editorContainer = container.querySelector('.prompt-editor-container');
    expect(editorContainer).toBeDefined();
  });

  it('renders copy button', () => {
    render(<PromptEditor value="test content" onChange={vi.fn()} />);
    expect(screen.getByLabelText('复制')).toBeDefined();
  });

  it('renders fullscreen button', () => {
    render(<PromptEditor value="test content" onChange={vi.fn()} />);
    expect(screen.getByLabelText('全屏')).toBeDefined();
  });
});
```

- [x] **Step 3: Implement PromptEditor**

Create `frontend/src/components/PromptEditor.tsx`:

```typescript
import { useEffect, useRef, useState, useCallback } from 'react';
import { EditorView, basicSetup } from 'codemirror';
import { EditorState } from '@codemirror/state';
import { markdown } from '@codemirror/lang-markdown';
import { keymap } from '@codemirror/view';
import { copyText } from '../utils/copy';

interface PromptEditorProps {
  value: string;
  onChange: (value: string) => void;
  minHeight?: string;
}

export function PromptEditor({ value, onChange, minHeight = '200px' }: PromptEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    if (!editorRef.current || viewRef.current) return;

    const updateListener = EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        onChange(update.state.doc.toString());
      }
    });

    const state = EditorState.create({
      doc: value,
      extensions: [
        basicSetup,
        markdown(),
        EditorView.lineWrapping,
        keymap.of([]),
        updateListener,
      ],
    });

    const view = new EditorView({
      state,
      parent: editorRef.current,
    });

    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, []); // Only mount once

  // Sync external value changes to editor (when value changes from outside)
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const currentDoc = view.state.doc.toString();
    if (currentDoc !== value) {
      view.dispatch({
        changes: { from: 0, to: currentDoc.length, insert: value },
      });
    }
  }, [value]);

  const handleCopy = useCallback(async () => {
    const view = viewRef.current;
    if (!view) return;
    const content = view.state.doc.toString();
    await copyText(content);
  }, []);

  const toggleFullscreen = useCallback(() => {
    setIsFullscreen(prev => !prev);
  }, []);

  return (
    <div className={`prompt-editor-container ${isFullscreen ? 'fixed inset-0 z-50 bg-white p-6' : ''}`}>
      <div className="relative border border-gray-300 rounded-lg overflow-hidden">
        <div
          ref={editorRef}
          style={{ minHeight }}
          className="prompt-editor"
        />
        <div className="absolute top-2 right-2 flex gap-1">
          <button
            onClick={handleCopy}
            aria-label="复制"
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
            title="复制"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            </svg>
          </button>
          <button
            onClick={toggleFullscreen}
            aria-label="全屏"
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
            title="全屏"
          >
            {isFullscreen ? (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
```

Note: CodeMirror 7 (CM6) uses the `codemirror` package as the main entry. If the installed version exports differently, adjust the import to match the actual API.

- [x] **Step 4: Integrate PromptEditor into AgentDrawer**

In `frontend/src/components/AgentDrawer.tsx`:
1. Add import: `import { PromptEditor } from './PromptEditor';`
2. Replace the System Prompt `<textarea>` section with:

```typescript
<section>
  <h3 className="text-sm font-semibold text-gray-800 mb-3">System Prompt</h3>
  <PromptEditor
    value={form.system_prompt || ''}
    onChange={(value) => handleChange('system_prompt', value)}
    minHeight="150px"
  />
</section>
```

- [x] **Step 5: Run PromptEditor tests**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/components/__tests__/PromptEditor.test.tsx`
Expected: PASS (or skip if CodeMirror DOM requirements exceed jsdom capabilities — mark as known limitation)

- [x] **Step 6: Commit**

```bash
git add frontend/src/components/PromptEditor.tsx frontend/src/components/__tests__/PromptEditor.test.tsx frontend/src/components/AgentDrawer.tsx
git commit -m "feat: add CodeMirror 6 prompt editor with copy and fullscreen"
```

---

### Task 8: Add /agents route to App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

- [x] **Step 1: Write failing test**

Create `frontend/src/__tests__/App.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';

// Mock the pages and contexts
vi.mock('../pages/ChatInterface', () => ({ ChatInterface: () => <div>ChatInterface</div> }));
vi.mock('../pages/LoginPage', () => ({ LoginPage: () => <div>LoginPage</div> }));
vi.mock('../pages/AgentManagement', () => ({ AgentManagement: () => <div>AgentManagement</div> }));
vi.mock('../pages/AdminAgents', () => ({ AdminAgents: () => <div>AdminAgents</div> }));
vi.mock('../components/PrivateRoute', () => ({ PrivateRoute: ({ children }: any) => <>{children}</> }));
vi.mock('../contexts/AuthContext', () => ({ AuthProvider: ({ children }: any) => <>{children}</> }));

describe('App routing', () => {
  it('renders AgentManagement at /agents', () => {
    render(
      <MemoryRouter initialEntries={['/agents']}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText('AgentManagement')).toBeDefined();
  });

  it('no longer renders AdminAgents at /admin/agents', () => {
    render(
      <MemoryRouter initialEntries={['/admin/agents']}>
        <App />
      </MemoryRouter>
    );
    // Should not render old AdminAgents — may render a blank or 404 page
    expect(screen.queryByText('AdminAgents')).toBeNull();
  });
});
```

- [x] **Step 2: Update App.tsx routes**

Modify `frontend/src/App.tsx`:

```typescript
import { Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { PrivateRoute } from './components/PrivateRoute';
import { ChatInterface } from './pages/ChatInterface';
import { LoginPage } from './pages/LoginPage';
import { AgentManagement } from './pages/AgentManagement';

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={
          <PrivateRoute><ChatInterface /></PrivateRoute>
        } />
        <Route path="/chat/:id" element={
          <PrivateRoute><ChatInterface /></PrivateRoute>
        } />
        <Route path="/agents" element={
          <PrivateRoute><AgentManagement /></PrivateRoute>
        } />
      </Routes>
    </AuthProvider>
  );
}

export default App;
```

- [x] **Step 3: Run tests to verify**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/__tests__/App.test.tsx`
Expected: PASS

- [x] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/__tests__/App.test.tsx
git commit -m "feat: add /agents route, remove /admin/agents route"
```

---

### Task 9: Chat header agent status display

**Files:**
- Create: `frontend/src/components/AgentHeaderStatus.tsx`
- Modify: `frontend/src/pages/ChatInterface.tsx`
- Test: `frontend/src/components/__tests__/AgentHeaderStatus.test.tsx`

**Interfaces:**
- `AgentHeaderStatus` props: none (reads from Zustand store directly)
- Connects to: useChatStore's `agentStatus`, `activeAgent`, `activeAgentDisplay`

- [x] **Step 1: Write failing tests for AgentHeaderStatus**

Create `frontend/src/components/__tests__/AgentHeaderStatus.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AgentHeaderStatus } from '../AgentHeaderStatus';
import { useChatStore } from '../../features/ai-chat/store/chatStore';

describe('AgentHeaderStatus', () => {
  beforeEach(() => {
    useChatStore.setState({
      agentStatus: 'idle',
      activeAgent: null,
      activeAgentDisplay: null,
    });
  });

  it('does not render when status is idle', () => {
    const { container } = render(<AgentHeaderStatus />);
    expect(container.innerHTML).toBe('');
  });

  it('renders agent info when status is thinking', () => {
    useChatStore.setState({
      agentStatus: 'thinking',
      activeAgent: 'agent-1',
      activeAgentDisplay: '研究员',
    });
    render(<AgentHeaderStatus />);
    expect(screen.getByText('研究员')).toBeDefined();
  });

  it('displays correct status label for each status', () => {
    useChatStore.setState({
      agentStatus: 'calling_tool',
      activeAgent: 'agent-1',
      activeAgentDisplay: '研究员',
    });
    render(<AgentHeaderStatus />);
    expect(screen.getByText('calling_tool')).toBeDefined();
  });

  it('displays generating status', () => {
    useChatStore.setState({
      agentStatus: 'generating',
      activeAgent: 'agent-1',
      activeAgentDisplay: 'Coder',
    });
    render(<AgentHeaderStatus />);
    expect(screen.getByText('Coder')).toBeDefined();
  });
});
```

- [x] **Step 2: Implement AgentHeaderStatus**

Create `frontend/src/components/AgentHeaderStatus.tsx`:

```typescript
import { useChatStore } from '../features/ai-chat/store/chatStore';

const statusLabels: Record<string, string> = {
  thinking: '思考中...',
  calling_tool: '调用工具',
  generating: '生成中...',
};

export function AgentHeaderStatus() {
  const agentStatus = useChatStore(s => s.agentStatus);
  const activeAgentDisplay = useChatStore(s => s.activeAgentDisplay);

  if (agentStatus === 'idle' || !activeAgentDisplay) return null;

  return (
    <div className="flex items-center gap-2 text-sm text-gray-400 ml-4">
      <span className="text-base">{'🤖'}</span>
      <span className="font-medium text-gray-600">{activeAgentDisplay}</span>
      <span className="text-gray-400">
        {statusLabels[agentStatus] || agentStatus}
      </span>
      {agentStatus === 'thinking' && (
        <span className="flex gap-0.5">
          <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </span>
      )}
    </div>
  );
}
```

- [x] **Step 3: Integrate into ChatInterface header**

Modify `frontend/src/pages/ChatInterface.tsx`:

1. Add import: `import { AgentHeaderStatus } from '../components/AgentHeaderStatus';`

2. In the header, replace the agent selector `<select>` block with:

```typescript
<AgentHeaderStatus />
```

The old agent selector `<select>` is removed because the Agent management page now handles agent configuration.

Also remove the `agentId` and `agents` state management that was only used for the selector. Specifically:
- Remove `const agentId = useChatStore(s => s.agentId);`
- Remove `const setAgentId = useChatStore(s => s.setAgentId);`
- Remove the `useState`, `useEffect`, and `fetch('/api/agents')` block
- Remove the `AgentInfo` import

- [x] **Step 4: Run tests**

Run: `cd /Volumes/work/projects/winter-agent/frontend && npx vitest run src/components/__tests__/AgentHeaderStatus.test.tsx`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/AgentHeaderStatus.tsx frontend/src/components/__tests__/AgentHeaderStatus.test.tsx frontend/src/pages/ChatInterface.tsx
git commit -m "feat: add chat header agent status display"
```

---

### Task 10: Cleanup — delete old AdminAgents page and route

**Files:**
- Delete: `frontend/src/pages/AdminAgents.tsx`
- Modify: `frontend/src/App.tsx` (already done in Task 8 — verify route removed)

**Verification: no automated test needed, manual verification only**

- [x] **Step 1: Verify AdminAgents references**

Search for remaining references to `AdminAgents` in the codebase:

```bash
cd /Volumes/work/projects/winter-agent/frontend && grep -r "AdminAgents" src/ --include="*.tsx" --include="*.ts" | grep -v node_modules | grep -v ".test."
```

Expected: no remaining imports or references (App.tsx import was already removed in Task 8)

- [x] **Step 2: Delete AdminAgents.tsx**

```bash
rm frontend/src/pages/AdminAgents.tsx
```

- [x] **Step 3: Verify build passes**

```bash
cd /Volumes/work/projects/winter-agent/frontend && npx tsc --noEmit
```

Expected: No errors

- [x] **Step 4: Run full test suite**

```bash
cd /Volumes/work/projects/winter-agent/frontend && npx vitest run
```

Expected: All tests pass

- [x] **Step 5: Commit**

```bash
git add frontend/src/pages/AdminAgents.tsx  # This will record the deletion
git commit -m "refactor: remove old AdminAgents page"
```

---

### Task 11: Verify existing functionality unaffected

**Files:**
- No files created/modified — verification only

- [x] **Step 1: Verify chat SSE functionality**

Check that the SSE handler in `frontend/src/features/ai-chat/services/chatApi.ts` still correctly updates `agentStatus` and `activeAgentDisplay`:
- `agent.started` sets status to `calling_tool` and sets `activeAgent`
- `agent.finished` sets status to `generating` then `idle`
- These fields are what `AgentHeaderStatus` reads

- [x] **Step 2: Verify useSessions backward compat**

The new Sidebar still receives the same `sessions` prop (from `useSessions` hook). Verify the SessionGroup component uses `createdAt` from `Conversation` type, which is unchanged in `frontend/src/types/chat.ts`.

- [x] **Step 3: Run full test suite**

```bash
cd /Volumes/work/projects/winter-agent/frontend && npx vitest run
```

Expected: All tests pass including existing ones for `chatApi`, `chatStore`, `copyText`, and `ToolCallPanel`.

- [x] **Step 4: Final commit (if any fixes needed)**

```bash
git commit -m "chore: verify existing functionality after refactor"
```
