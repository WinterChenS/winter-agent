import { useState, useEffect, useCallback } from 'react';
import { agentApi } from '../services/agent';
import type { AgentInfo, AgentCreateRequest } from '../types/agent';

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

  const createAgent = useCallback(async (data: AgentCreateRequest): Promise<AgentInfo | null> => {
    try {
      const agent = await agentApi.createAgent(data);
      await fetchAgents();
      return agent;
    } catch {
      return null;
    }
  }, [fetchAgents]);

  const updateAgent = useCallback(async (id: string, data: Partial<AgentCreateRequest>): Promise<AgentInfo | null> => {
    try {
      const agent = await agentApi.updateAgent(id, data);
      await fetchAgents();
      return agent;
    } catch {
      return null;
    }
  }, [fetchAgents]);

  const deleteAgent = useCallback(async (id: string): Promise<boolean> => {
    try {
      await agentApi.deleteAgent(id);
      await fetchAgents();
      return true;
    } catch {
      return false;
    }
  }, [fetchAgents]);

  const toggleAgent = useCallback(async (id: string, enabled: boolean): Promise<AgentInfo | null> => {
    try {
      const agent = await agentApi.toggleAgent(id, enabled);
      await fetchAgents();
      return agent;
    } catch {
      return null;
    }
  }, [fetchAgents]);

  const cloneAgent = useCallback(async (id: string): Promise<AgentInfo | null> => {
    try {
      const agent = await agentApi.cloneAgent(id);
      await fetchAgents();
      return agent;
    } catch {
      return null;
    }
  }, [fetchAgents]);

  return {
    agents,
    loading,
    error,
    fetchAgents,
    createAgent,
    updateAgent,
    deleteAgent,
    toggleAgent,
    cloneAgent,
  };
}
