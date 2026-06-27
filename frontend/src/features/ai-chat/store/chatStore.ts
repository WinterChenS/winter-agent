// frontend/src/features/ai-chat/store/chatStore.ts
import { create } from 'zustand';
import type { Message, ToolCall } from '../types/message';

interface ChatState {
  messages: Record<string, Message>;
  messageOrder: string[];
  agentId: string | null;
  conversationId: string | null;
  isSending: boolean;
  agentStatus: 'idle' | 'thinking' | 'calling_tool' | 'generating';
  activeAgent: string | null;
  activeAgentDisplay: string | null;

  addMessage: (msg: Message) => void;
  appendDelta: (id: string, delta: string) => void;
  appendReasoning: (id: string, delta: string) => void;
  upsertToolCall: (messageId: string, toolCall: ToolCall) => void;
  addImage: (messageId: string, filename: string, url: string) => void;
  completeMessage: (id: string, status: "done" | "error") => void;
  setAgentId: (id: string) => void;
  setConversationId: (id: string) => void;
  setIsSending: (v: boolean) => void;
  setAgentStatus: (status: ChatState['agentStatus']) => void;
  setActiveAgent: (name: string | null, display: string | null) => void;
  loadHistory: (msgs: Message[]) => void;
  clearMessages: () => void;
}

// rAF batching state (module-level, outside React)
let pendingDeltas = new Map<string, string>();
let pendingReasonings = new Map<string, string>();
let rafId: number | null = null;

function flushBatched() {
  useChatStore.setState(state => {
    const messages = { ...state.messages };
    for (const [msgId, text] of pendingDeltas) {
      if (messages[msgId]) {
        messages[msgId] = { ...messages[msgId], content: messages[msgId].content + text };
      }
    }
    for (const [msgId, text] of pendingReasonings) {
      if (messages[msgId]) {
        messages[msgId] = {
          ...messages[msgId],
          reasoning: (messages[msgId].reasoning || '') + text,
        };
      }
    }
    return { messages };
  });
  pendingDeltas.clear();
  pendingReasonings.clear();
  rafId = null;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: {},
  messageOrder: [],
  agentId: null,
  conversationId: null,
  isSending: false,
  agentStatus: 'idle',
  activeAgent: null,
  activeAgentDisplay: null,

  addMessage: (msg) => set(state => ({
    messages: { ...state.messages, [msg.id]: msg },
    messageOrder: [...state.messageOrder, msg.id],
  })),

  appendDelta: (id, delta) => {
    pendingDeltas.set(id, (pendingDeltas.get(id) || '') + delta);
    if (rafId === null) {
      rafId = requestAnimationFrame(flushBatched);
    }
  },

  appendReasoning: (id, delta) => {
    pendingReasonings.set(id, (pendingReasonings.get(id) || '') + delta);
    if (rafId === null) {
      rafId = requestAnimationFrame(flushBatched);
    }
  },

  upsertToolCall: (messageId, toolCall) => set(state => {
    const msg = state.messages[messageId];
    if (!msg) return state;
    const existing = msg.toolCalls || [];
    const idx = existing.findIndex(tc => tc.id === toolCall.id);
    const updated = idx >= 0
      ? [...existing.slice(0, idx), { ...existing[idx], ...toolCall }, ...existing.slice(idx + 1)]
      : [...existing, toolCall];
    return {
      messages: { ...state.messages, [messageId]: { ...msg, toolCalls: updated } }
    };
  }),

  addImage: (messageId, filename, url) => set(state => {
    const msg = state.messages[messageId];
    if (!msg) return state;
    const images = { ...(msg.images || {}), [filename]: url };
    return { messages: { ...state.messages, [messageId]: { ...msg, images } } };
  }),
  completeMessage: (id, status) => set(state => {
    const msg = state.messages[id];
    if (!msg) return state;
    return { messages: { ...state.messages, [id]: { ...msg, status } } };
  }),

  setAgentId: (agentId) => set({ agentId }),
  setConversationId: (id) => set({ conversationId: id }),
  setIsSending: (v) => set({ isSending: v }),
  setAgentStatus: (status) => set({ agentStatus: status }),
  setActiveAgent: (name, display) => set({ activeAgent: name, activeAgentDisplay: display }),

  loadHistory: (msgs) => {
    const messages: Record<string, Message> = {};
    const messageOrder: string[] = [];
    for (const m of msgs) {
      messages[m.id] = m;
      messageOrder.push(m.id);
    }
    set({ messages, messageOrder });
  },

  clearMessages: () => set({ messages: {}, messageOrder: [] }),
}));
