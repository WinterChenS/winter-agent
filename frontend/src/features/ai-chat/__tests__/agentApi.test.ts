import { describe, it, expect, vi, beforeEach } from 'vitest';
import { agentApi } from '../services/agent';

// Polyfill localStorage for Node test environment (restoreAllMocks-safe)
const storageStore: Record<string, string> = {};
Object.defineProperty(globalThis, 'localStorage', {
  value: {
    getItem: (key: string) => storageStore[key] ?? null,
    setItem: (key: string, value: string) => { storageStore[key] = value; },
    removeItem: (key: string) => { delete storageStore[key]; },
    clear: () => { Object.keys(storageStore).forEach(k => delete storageStore[k]); },
    key: (index: number) => Object.keys(storageStore)[index] ?? null,
    get length() { return Object.keys(storageStore).length; },
  },
  writable: true,
  configurable: true,
});

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

  it('getAgent returns agent by id', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockAgent),
    } as Response);

    const agent = await agentApi.getAgent('agent-1');
    expect(agent.name).toBe('researcher');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/agents/agent-1',
      expect.anything()
    );
  });

  it('getAgent throws on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 404,
    } as Response);

    await expect(agentApi.getAgent('agent-1')).rejects.toThrow('Failed to fetch agent: 404');
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
      '/api/agents/',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('createAgent throws on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
    } as Response);

    await expect(agentApi.createAgent({ name: 'bad', display_name: 'Bad' })).rejects.toThrow(
      'Failed to create agent: 400'
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
      '/api/agents/agent-1',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('updateAgent throws on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 500,
    } as Response);

    await expect(agentApi.updateAgent('agent-1', {})).rejects.toThrow(
      'Failed to update agent: 500'
    );
  });

  it('deleteAgent sends DELETE', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
    } as Response);

    await agentApi.deleteAgent('agent-1');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/agents/agent-1',
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('deleteAgent throws on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 404,
    } as Response);

    await expect(agentApi.deleteAgent('agent-1')).rejects.toThrow('Failed to delete agent: 404');
  });

  it('toggleAgent calls updateAgent with enabled toggle', async () => {
    vi.spyOn(agentApi, 'updateAgent').mockResolvedValueOnce({
      ...mockAgent,
      enabled: false,
    });
    const result = await agentApi.toggleAgent('agent-1', false);
    expect(result.enabled).toBe(false);
    expect(agentApi.updateAgent).toHaveBeenCalledWith('agent-1', { enabled: false });
  });

  it('cloneAgent calls POST /api/agents/{id}/clone and returns the cloned agent', async () => {
    const clonedAgent = {
      ...mockAgent,
      id: 'agent-copy',
      name: 'researcher-copy',
    };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(clonedAgent),
    } as Response);

    const result = await agentApi.cloneAgent('agent-1');
    expect(result.name).toBe('researcher-copy');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/agents/agent-1/clone',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('cloneAgent throws on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 404,
    } as Response);

    await expect(agentApi.cloneAgent('agent-1')).rejects.toThrow('Failed to clone agent: 404');
  });
});
