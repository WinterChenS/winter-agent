import { useCallback } from 'react';
import { useChatStore } from '../store/chatStore';
import { apiFetch } from '../../../services/api';
import type { ToolCall } from '../types/message';
import type { Message } from '../types/message';

function normalizeToolCalls(toolCalls: unknown): ToolCall[] {
  if (!toolCalls) return [];
  if (typeof toolCalls === 'string') {
    try {
      return JSON.parse(toolCalls);
    } catch {
      return [];
    }
  }
  return Array.isArray(toolCalls) ? (toolCalls as ToolCall[]) : [];
}

function normalizeMessage(msg: Record<string, unknown>): Message {
  return {
    id: msg.id as string,
    role: (msg.role as Message['role']) || 'assistant',
    content: (msg.content as string) || '',
    reasoning: (msg.reasoning as string) || undefined,
    status: (msg.status as Message['status']) || 'done',
    toolCalls: normalizeToolCalls(msg.toolCalls),
    agentId: (msg.agentId as string) || undefined,
    conversationId: (msg.conversationId as string) || undefined,
    createdAt: typeof msg.createdAt === 'number' ? msg.createdAt : undefined,
    images: (msg.images as Message['images']) || {},
  };
}

export function useConversation() {
  const loadHistory = useCallback(async (conversationId: string) => {
    const token = localStorage.getItem('auth_token');
    const res = await apiFetch(`/api/chat/history/${conversationId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Failed to load history');
    const data = await res.json();
    if (data.messages) {
      const normalized = (data.messages as Record<string, unknown>[]).map(normalizeMessage);
      useChatStore.getState().loadHistory(normalized);
    }
    useChatStore.getState().setConversationId(conversationId);
  }, []);

  return { loadHistory };
}
