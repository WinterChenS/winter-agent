import { useCallback } from 'react';
import { generateUUID } from '../../../utils/uuid';
import { useChatStore } from '../store/chatStore';
import { sendChatMessage } from '../services/chatApi';

export function useChatStream() {
  const isSending = useChatStore(s => s.isSending);

  const send = useCallback(async (content: string) => {
    const { agentId, conversationId, isSending } = useChatStore.getState();
    if (!content.trim() || isSending) return;

    const messageId = generateUUID();
    const now = Date.now();

    useChatStore.getState().addMessage({
      id: generateUUID(), role: 'user', content: content.trim(),
      rawContent: content.trim(), status: 'done', createdAt: now,
    });

    useChatStore.getState().addMessage({
      id: messageId, role: 'assistant', content: '',
      status: 'streaming', agentId: agentId || undefined,
      conversationId: conversationId || undefined, createdAt: now,
    });

    useChatStore.getState().setIsSending(true);

    try {
      await sendChatMessage({ message: content.trim(), agentId, conversationId, messageId });
    } catch (err) {
      useChatStore.getState().completeMessage(messageId, 'error');
      useChatStore.getState().setIsSending(false);
    }
  }, []);

  return { send, isSending };
}
