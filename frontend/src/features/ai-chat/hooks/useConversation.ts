import { useCallback } from 'react';
import { useChatStore } from '../store/chatStore';

export function useConversation() {
  const loadHistory = useCallback(async (conversationId: string) => {
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`/api/chat/history/${conversationId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Failed to load history');
    const data = await res.json();
    if (data.messages) {
      useChatStore.getState().loadHistory(data.messages);
    }
    useChatStore.getState().setConversationId(conversationId);
  }, []);

  return { loadHistory };
}
