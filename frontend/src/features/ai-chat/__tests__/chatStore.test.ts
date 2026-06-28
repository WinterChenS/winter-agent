import { describe, it, expect, beforeEach, vi, beforeAll, afterAll } from 'vitest';
import { useChatStore } from '../store/chatStore';

// Polyfill requestAnimationFrame for Node test environment
beforeAll(() => {
  (globalThis as any).requestAnimationFrame = (cb: FrameRequestCallback) => {
    return setTimeout(cb, 16) as unknown as number;
  };
  (globalThis as any).cancelAnimationFrame = (id: number) => {
    clearTimeout(id);
  };
});

afterAll(() => {
  delete (globalThis as any).requestAnimationFrame;
  delete (globalThis as any).cancelAnimationFrame;
});

describe('chatStore', () => {
  beforeEach(() => {
    useChatStore.getState().clearMessages();
    useChatStore.setState({ agentId: null, conversationId: null, isSending: false });
  });

  it('addMessage adds message to messages map and appends id to messageOrder', () => {
    const id = 'msg-1';
    useChatStore.getState().addMessage({
      id,
      role: 'user',
      content: 'hi',
      status: 'done',
    });

    const state = useChatStore.getState();
    expect(state.messages[id]).toBeDefined();
    expect(state.messages[id].content).toBe('hi');
    expect(state.messages[id].role).toBe('user');
    expect(state.messageOrder).toContain(id);
  });

  it('appendDelta accumulates content via requestAnimationFrame batching', () => {
    // Use fake timers so we can control requestAnimationFrame timing
    vi.useFakeTimers();

    useChatStore.getState().addMessage({
      id: 'msg-2',
      role: 'assistant',
      content: '',
      status: 'streaming',
    });

    useChatStore.getState().appendDelta('msg-2', 'Hello');
    useChatStore.getState().appendDelta('msg-2', ' World');

    // Advance timers to flush the rAF callback (16ms default for rAF)
    vi.advanceTimersByTime(20);

    const state = useChatStore.getState();
    expect(state.messages['msg-2'].content).toBe('Hello World');

    vi.useRealTimers();
  });

  it('appendDelta does nothing for unknown message id', () => {
    vi.useFakeTimers();

    useChatStore.getState().appendDelta('nonexistent', 'test');
    vi.advanceTimersByTime(20);

    // Should not throw
    const state = useChatStore.getState();
    expect(Object.keys(state.messages).length).toBe(0);

    vi.useRealTimers();
  });

  it('upsertToolCall adds new tool call when id does not exist', () => {
    useChatStore.getState().addMessage({
      id: 'msg-3',
      role: 'assistant',
      content: '',
      status: 'streaming',
    });

    useChatStore.getState().upsertToolCall('msg-3', {
      id: 'tc-1',
      name: 'search',
      arguments: { q: 'test' },
      status: 'running',
    });

    const state = useChatStore.getState();
    const tcs = state.messages['msg-3'].toolCalls ?? [];
    expect(tcs).toHaveLength(1);
    expect(tcs[0].id).toBe('tc-1');
    expect(tcs[0].name).toBe('search');
    expect(tcs[0].status).toBe('running');
  });

  it('upsertToolCall merges fields when id already exists', () => {
    useChatStore.getState().addMessage({
      id: 'msg-3',
      role: 'assistant',
      content: '',
      status: 'streaming',
    });

    // First insert
    useChatStore.getState().upsertToolCall('msg-3', {
      id: 'tc-1',
      name: 'search',
      arguments: { q: 'test' },
      status: 'running',
    });

    // Update with status change and result
    useChatStore.getState().upsertToolCall('msg-3', {
      id: 'tc-1',
      name: 'search',
      arguments: {},
      status: 'done',
      result: 'found result',
    });

    const state = useChatStore.getState();
    const tcs = state.messages['msg-3'].toolCalls ?? [];
    expect(tcs).toHaveLength(1);
    expect(tcs[0].status).toBe('done');
    expect(tcs[0].result).toBe('found result');
    // Merged object keeps same id and name
    expect(tcs[0].id).toBe('tc-1');
    expect(tcs[0].name).toBe('search');
  });

  it('upsertToolCall adds multiple distinct tool calls', () => {
    useChatStore.getState().addMessage({
      id: 'msg-3',
      role: 'assistant',
      content: '',
      status: 'streaming',
    });

    useChatStore.getState().upsertToolCall('msg-3', {
      id: 'tc-1', name: 'search', arguments: {}, status: 'running',
    });
    useChatStore.getState().upsertToolCall('msg-3', {
      id: 'tc-2', name: 'calculator', arguments: {}, status: 'running',
    });

    const state = useChatStore.getState();
    const tcs = state.messages['msg-3'].toolCalls ?? [];
    expect(tcs).toHaveLength(2);
  });

  it('upsertToolCall does nothing for unknown message id', () => {
    useChatStore.getState().upsertToolCall('nonexistent', {
      id: 'tc-1', name: 'test', arguments: {}, status: 'running',
    });

    // State should remain unchanged
    const state = useChatStore.getState();
    expect(Object.keys(state.messages).length).toBe(0);
  });

  it('completeMessage sets status on existing message', () => {
    useChatStore.getState().addMessage({
      id: 'msg-4',
      role: 'assistant',
      content: 'hello',
      status: 'streaming',
    });

    useChatStore.getState().completeMessage('msg-4', 'done');
    expect(useChatStore.getState().messages['msg-4'].status).toBe('done');
  });

  it('completeMessage handles error status', () => {
    useChatStore.getState().addMessage({
      id: 'msg-4',
      role: 'assistant',
      content: '',
      status: 'streaming',
    });

    useChatStore.getState().completeMessage('msg-4', 'error');
    expect(useChatStore.getState().messages['msg-4'].status).toBe('error');
  });

  it('completeMessage does nothing for unknown message id', () => {
    useChatStore.getState().completeMessage('nonexistent', 'done');
    // Should not throw or change state
    const state = useChatStore.getState();
    expect(Object.keys(state.messages).length).toBe(0);
  });

  it('completeMessage sets rawContent from content when status is done', () => {
    useChatStore.getState().addMessage({
      id: 'msg-raw',
      role: 'assistant',
      content: 'Hello **world**',
      status: 'streaming',
    });
    useChatStore.getState().completeMessage('msg-raw', 'done');
    const msg = useChatStore.getState().messages['msg-raw'];
    expect(msg.rawContent).toBe('Hello **world**');
  });

  it('completeMessage error status does not set rawContent', () => {
    useChatStore.getState().addMessage({
      id: 'msg-err2',
      role: 'assistant',
      content: 'partial',
      status: 'streaming',
    });
    useChatStore.getState().completeMessage('msg-err2', 'error');
    const msg = useChatStore.getState().messages['msg-err2'];
    expect(msg.rawContent).toBeUndefined();
  });

  it('setAgentId updates agentId', () => {
    expect(useChatStore.getState().agentId).toBeNull();
    useChatStore.getState().setAgentId('agent-7');
    expect(useChatStore.getState().agentId).toBe('agent-7');
  });

  it('setAgentId accepts null to clear selection', () => {
    useChatStore.getState().setAgentId('agent-7');
    useChatStore.getState().setAgentId(null as unknown as string);
    expect(useChatStore.getState().agentId).toBeNull();
  });

  it('setConversationId updates conversationId', () => {
    expect(useChatStore.getState().conversationId).toBeNull();
    useChatStore.getState().setConversationId('conv-1');
    expect(useChatStore.getState().conversationId).toBe('conv-1');
  });

  it('setIsSending toggles sending state', () => {
    expect(useChatStore.getState().isSending).toBe(false);
    useChatStore.getState().setIsSending(true);
    expect(useChatStore.getState().isSending).toBe(true);
    useChatStore.getState().setIsSending(false);
    expect(useChatStore.getState().isSending).toBe(false);
  });

  it('loadHistory populates messages and order', () => {
    const msgs = [
      { id: 'm1', role: 'user' as const, content: 'hello', status: 'done' as const, createdAt: 1000 },
      { id: 'm2', role: 'assistant' as const, content: 'world', status: 'done' as const, createdAt: 2000 },
    ];

    useChatStore.getState().loadHistory(msgs);

    const state = useChatStore.getState();
    expect(state.messageOrder).toEqual(['m1', 'm2']);
    expect(state.messages['m1'].content).toBe('hello');
    expect(state.messages['m2'].content).toBe('world');
  });

  it('clearMessages resets messages and order', () => {
    useChatStore.getState().addMessage({
      id: 'm1', role: 'user', content: 'hello', status: 'done',
    });

    useChatStore.getState().clearMessages();
    const state = useChatStore.getState();
    expect(Object.keys(state.messages).length).toBe(0);
    expect(state.messageOrder.length).toBe(0);
  });
});

describe('loadHistory validation', () => {
  it('skips messages with null/empty id', () => {
    const msgs = [
      { id: 'm1', role: 'user' as const, content: 'hi', status: 'done' as const },
      { id: '', role: 'user' as const, content: 'bad', status: 'done' as const },
      { id: null as unknown as string, role: 'user' as const, content: 'bad2', status: 'done' as const },
    ];
    useChatStore.getState().loadHistory(msgs as any);
    const state = useChatStore.getState();
    expect(state.messageOrder).toEqual(['m1']);
  });

  it('deduplicates messages by id', () => {
    const msgs = [
      { id: 'm1', role: 'user' as const, content: 'first', status: 'done' as const },
      { id: 'm1', role: 'user' as const, content: 'duplicate', status: 'done' as const },
    ];
    useChatStore.getState().loadHistory(msgs);
    const state = useChatStore.getState();
    expect(state.messageOrder).toEqual(['m1']);
    expect(state.messages['m1'].content).toBe('first');
  });

  it('forces status to done for all history messages', () => {
    const msgs = [
      { id: 'm1', role: 'user' as const, content: 'hi', status: 'streaming' as const },
    ];
    useChatStore.getState().loadHistory(msgs);
    expect(useChatStore.getState().messages['m1'].status).toBe('done');
  });
});

describe('normalizeToolCalls', () => {
  it('handles toolCalls as JSON string', () => {
    const msgs = [{
      id: 'm1', role: 'assistant' as const, content: '',
      status: 'done' as const,
      toolCalls: '[{"id":"tc-1","name":"search","arguments":{},"status":"done"}]',
    }];
    useChatStore.getState().loadHistory(msgs as any);
    const tcs = useChatStore.getState().messages['m1'].toolCalls ?? [];
    expect(tcs).toHaveLength(1);
    expect(tcs[0].name).toBe('search');
  });

  it('handles already-parsed toolCalls array', () => {
    const msgs = [{
      id: 'm2', role: 'assistant' as const, content: '',
      status: 'done' as const,
      toolCalls: [{ id: 'tc-1', name: 'search', arguments: {}, status: 'done' }],
    }];
    useChatStore.getState().loadHistory(msgs as any);
    const tcs = useChatStore.getState().messages['m2'].toolCalls ?? [];
    expect(tcs).toHaveLength(1);
  });

  it('returns empty array for null toolCalls', () => {
    const msgs = [{
      id: 'm3', role: 'assistant' as const, content: '',
      status: 'done' as const,
      toolCalls: null,
    }];
    useChatStore.getState().loadHistory(msgs as any);
    const tcs = useChatStore.getState().messages['m3'].toolCalls ?? [];
    expect(tcs).toEqual([]);
  });

  it('returns empty array for malformed JSON string', () => {
    const msgs = [{
      id: 'm4', role: 'assistant' as const, content: '',
      status: 'done' as const,
      toolCalls: 'not valid json',
    }];
    useChatStore.getState().loadHistory(msgs as any);
    const tcs = useChatStore.getState().messages['m4'].toolCalls ?? [];
    expect(tcs).toEqual([]);
  });
});
