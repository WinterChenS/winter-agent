// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAgent } from '../hooks/useAgent';
import { agentApi } from '../services/agent';

vi.mock('../services/agent', () => ({
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
    const newAgent = { id: '3', name: 'new', display_name: 'New', description: '', enabled: true };
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);
    vi.mocked(agentApi.createAgent).mockResolvedValueOnce(newAgent);
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce([...mockAgents, newAgent]);

    const { result } = renderHook(() => useAgent());

    await waitFor(() => expect(result.current.loading).toBe(false));

    let ret: unknown;
    await act(async () => {
      ret = await result.current.createAgent({ name: 'new', display_name: 'New' });
    });

    expect(ret).toEqual(newAgent);
    expect(agentApi.createAgent).toHaveBeenCalledWith({ name: 'new', display_name: 'New' });
    expect(result.current.agents).toHaveLength(3);
  });

  it('updateAgent calls API and refreshes list', async () => {
    const updated = { ...mockAgents[0], description: 'updated' };
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);
    vi.mocked(agentApi.updateAgent).mockResolvedValueOnce(updated);
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce([updated, mockAgents[1]]);

    const { result } = renderHook(() => useAgent());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let ret: unknown;
    await act(async () => {
      ret = await result.current.updateAgent('1', { description: 'updated' });
    });

    expect(ret).toEqual(updated);
    expect(agentApi.updateAgent).toHaveBeenCalledWith('1', { description: 'updated' });
  });

  it('deleteAgent calls API and refreshes list', async () => {
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);
    vi.mocked(agentApi.deleteAgent).mockResolvedValueOnce(undefined);
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce([mockAgents[1]]);

    const { result } = renderHook(() => useAgent());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let ret: unknown;
    await act(async () => {
      ret = await result.current.deleteAgent('1');
    });

    expect(ret).toBe(true);
    expect(agentApi.deleteAgent).toHaveBeenCalledWith('1');
    expect(result.current.agents).toHaveLength(1);
  });

  it('toggleAgent toggles enabled state', async () => {
    const toggled = { ...mockAgents[0], enabled: false };
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);
    vi.mocked(agentApi.toggleAgent).mockResolvedValueOnce(toggled);
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce([toggled, mockAgents[1]]);

    const { result } = renderHook(() => useAgent());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let ret: unknown;
    await act(async () => {
      ret = await result.current.toggleAgent('1', false);
    });

    expect(ret).toEqual(toggled);
    expect(agentApi.toggleAgent).toHaveBeenCalledWith('1', false);
  });

  it('cloneAgent calls clone and refreshes list', async () => {
    const cloned = { id: '3', name: 'agent-1-copy', display_name: 'Agent 1 copy', description: '', enabled: true };
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce(mockAgents);
    vi.mocked(agentApi.cloneAgent).mockResolvedValueOnce(cloned);
    vi.mocked(agentApi.listAgents).mockResolvedValueOnce([...mockAgents, cloned]);

    const { result } = renderHook(() => useAgent());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let ret: unknown;
    await act(async () => {
      ret = await result.current.cloneAgent('1');
    });

    expect(ret).toEqual(cloned);
    expect(agentApi.cloneAgent).toHaveBeenCalledWith('1');
    expect(result.current.agents).toHaveLength(3);
  });
});
