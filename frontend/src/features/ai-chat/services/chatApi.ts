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
  schemaVersion?: string;
  conversationId?: string;
  agentId?: string;
  timestamp?: number;
  payload?: Record<string, unknown>;
  // Flat fallback fields (legacy compatibility)
  messageId?: string;
  agent?: string;
  display?: string;
  delta?: string;
  toolCall?: ToolCall;
  status?: string;
  error?: string;
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

  if (response.status === 401) {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_username');
    window.location.href = '/login';
    return;
  }
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
  // Merge top-level AND payload fields: bus_runner puts messageId at top level,
  // LangGraph events put it in payload. Payload takes priority when both exist.
  const p = { ...event, ...(event.payload || {}) } as Record<string, unknown>;
  const { type } = event;
  const messageId = (p.messageId as string) || undefined;
  const delta = (p.delta as string) || undefined;
  const toolCall = p.toolCall as ToolCall | undefined;
  const status = (p.status as string) || undefined;
  const store = useChatStore.getState();

  switch (type) {
    case 'conversation.started':
      store.setAgentStatus('thinking');
      break;

    case 'agent.started':
      store.setAgentStatus('calling_tool');
      store.setActiveAgent(p.agent as string, p.display as string);
      break;

    case 'agent.finished':
      store.setActiveAgent(null, null);
      store.setAgentStatus('generating');
      break;

    case 'tool.started': {
      const tcId = (p.tool_call_id as string) || '';
      if (messageId && tcId) {
        store.upsertToolCall(messageId, {
          id: tcId,
          name: (p.tool as string) || 'unknown',
          arguments: (p.arguments as Record<string, unknown>) || {},
          status: 'running',
        });
      }
      break;
    }

    case 'tool.finished': {
      const tcId2 = (p.tool_call_id as string) || '';
      if (messageId && tcId2) {
        store.upsertToolCall(messageId, {
          id: tcId2,
          name: (p.tool as string) || 'unknown',
          status: 'done',
          result: p.result,
        });
      }
      break;
    }

    case 'tool.failed': {
      const tcId3 = (p.tool_call_id as string) || '';
      if (messageId && tcId3) {
        store.upsertToolCall(messageId, {
          id: tcId3,
          name: (p.tool as string) || 'unknown',
          status: 'failed',
          result: p.error,
        });
      }
      break;
    }

    case 'image.uploaded':
      if (messageId) {
        const url = p.url as string;
        const filename = p.filename as string;
        if (url) store.addImage(messageId, filename, url);
      }
      break;

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
