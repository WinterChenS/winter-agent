// frontend/src/features/ai-chat/services/chatApi.ts
import { useChatStore } from '../store/chatStore';
import type { ToolCall } from '../types/message';

interface ChatRequest {
  message: string;
  agentId: string | null;
  conversationId: string | null;
  messageId: string;
}

interface SseEvent {
  type: string;
  messageId?: string;
  agentId?: string;
  delta?: string;
  toolCall?: ToolCall;
  status?: string;
  error?: string;
  payload?: Record<string, unknown>;
}

export async function sendChatMessage(req: ChatRequest): Promise<void> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      message: req.message,
      agentId: req.agentId,
      conversationId: req.conversationId,
      messageId: req.messageId,
    }),
  });

  if (!response.ok) throw new Error(`Chat request failed: ${response.status}`);
  if (!response.body) throw new Error('Empty response body');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data:')) continue;

        const data = trimmed.startsWith('data: ')
          ? trimmed.slice(6)
          : trimmed.slice(5);
        if (data === '[DONE]') continue;

        try {
          const event: SseEvent = JSON.parse(data);
          handleEvent(event);
        } catch {
          console.warn('SSE parse error:', data);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function handleEvent(event: SseEvent): void {
  const { type, messageId, delta, toolCall, status } = event;
  const payload = event.payload || {};
  const store = useChatStore.getState();

  switch (type) {
    case 'conversation.started':
      store.setAgentStatus('thinking');
      break;

    case 'agent.started':
      store.setAgentStatus('calling_tool');
      store.setActiveAgent(payload.agent as string, payload.display as string);
      break;

    case 'agent.finished':
      store.setActiveAgent(null, null);
      store.setAgentStatus('generating');
      break;

    case 'tool.started': {
      const tcId = (payload.tool_call_id as string) || '';
      if (messageId && tcId) {
        store.upsertToolCall(messageId, {
          id: tcId,
          name: (payload.tool as string) || 'unknown',
          arguments: (payload.arguments as Record<string, unknown>) || {},
          status: 'running',
        });
      }
      break;
    }

    case 'tool.finished': {
      const tcId2 = (payload.tool_call_id as string) || '';
      if (messageId && tcId2) {
        store.upsertToolCall(messageId, {
          id: tcId2,
          name: (payload.tool as string) || 'unknown',
          status: 'done',
          result: payload.result,
        });
      }
      break;
    }

    case 'tool.failed': {
      const tcId3 = (payload.tool_call_id as string) || '';
      if (messageId && tcId3) {
        store.upsertToolCall(messageId, {
          id: tcId3,
          name: (payload.tool as string) || 'unknown',
          status: 'failed',
          result: payload.error,
        });
      }
      break;
    }

    case 'message.tool_call':
      if (messageId && toolCall) store.upsertToolCall(messageId, toolCall);
      break;

    case 'message.delta':
      if (messageId && delta) store.appendDelta(messageId, delta);
      break;

    case 'message.reasoning':
      if (messageId && delta) store.appendReasoning(messageId, delta);
      break;

    case 'message.done':
    case 'conversation.finished':
      if (messageId && status) {
        store.completeMessage(messageId, status as 'done' | 'error');
      }
      store.setIsSending(false);
      store.setAgentStatus('idle');
      break;

    case 'error':
      if (messageId) store.completeMessage(messageId, 'error');
      store.setIsSending(false);
      break;

    default:
      // Ignore legacy event types
  }
}
