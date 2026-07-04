import { apiFetch } from '../../../services/api';
import type { AgentInfo, AgentCreateRequest } from '../types/agent';

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export const agentApi = {
  async listAgents(): Promise<AgentInfo[]> {
    const res = await apiFetch('/api/agents', { headers: authHeaders() });
    if (!res.ok) throw new Error(`Failed to fetch agents: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  },

  async getAgent(id: string): Promise<AgentInfo> {
    const res = await apiFetch(`/api/agents/${id}`, { headers: authHeaders() });
    if (!res.ok) throw new Error(`Failed to fetch agent: ${res.status}`);
    return res.json();
  },

  async createAgent(data: AgentCreateRequest): Promise<AgentInfo> {
    const res = await apiFetch('/api/agents', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`Failed to create agent: ${res.status}`);
    return res.json();
  },

  async updateAgent(id: string, data: Partial<AgentCreateRequest>): Promise<AgentInfo> {
    const res = await apiFetch(`/api/agents/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`Failed to update agent: ${res.status}`);
    return res.json();
  },

  async deleteAgent(id: string): Promise<void> {
    const res = await apiFetch(`/api/agents/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error(`Failed to delete agent: ${res.status}`);
  },

  async toggleAgent(id: string, enabled: boolean): Promise<AgentInfo> {
    return agentApi.updateAgent(id, { enabled });
  },

  async cloneAgent(id: string): Promise<AgentInfo> {
    const res = await apiFetch(`/api/agents/${id}/clone`, { method: 'POST', headers: authHeaders() });
    if (!res.ok) throw new Error(`Failed to clone agent: ${res.status}`);
    return res.json();
  },
};
