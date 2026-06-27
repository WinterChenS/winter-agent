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

describe('SSE event field resolution', () => {
  beforeEach(() => {
    useChatStore.getState().clearMessages();
  });

  it('prepares message for payload-wrapped delta events', () => {
    vi.useFakeTimers();

    const msgId = 'msg-delta-1';
    useChatStore.getState().addMessage({
      id: msgId, role: 'assistant', content: '', status: 'streaming',
    });

    useChatStore.getState().appendDelta(msgId, 'Hello from payload');

    vi.advanceTimersByTime(20);

    const state = useChatStore.getState();
    expect(state.messages[msgId].content).toBe('Hello from payload');

    vi.useRealTimers();
  });

  it('prepares message for flat legacy events', () => {
    vi.useFakeTimers();

    const msgId = 'msg-flat-1';
    useChatStore.getState().addMessage({
      id: msgId, role: 'assistant', content: '', status: 'streaming',
    });

    useChatStore.getState().appendDelta(msgId, 'Hello from flat');

    vi.advanceTimersByTime(20);

    const state = useChatStore.getState();
    expect(state.messages[msgId].content).toBe('Hello from flat');

    vi.useRealTimers();
  });

  it('handles tool.started with payload-wrapped fields', () => {
    const msgId = 'msg-tool-1';
    useChatStore.getState().addMessage({
      id: msgId, role: 'assistant', content: '', status: 'streaming',
    });

    useChatStore.getState().upsertToolCall(msgId, {
      id: 'tc-payload-1',
      name: 'search',
      arguments: { q: 'test' },
      status: 'running',
    });

    const tcs = useChatStore.getState().messages[msgId].toolCalls ?? [];
    expect(tcs).toHaveLength(1);
    expect(tcs[0].id).toBe('tc-payload-1');
    expect(tcs[0].name).toBe('search');
  });

  it('handles image.uploaded with payload fields', () => {
    const msgId = 'msg-img-1';
    useChatStore.getState().addMessage({
      id: msgId, role: 'assistant', content: '', status: 'streaming',
    });

    useChatStore.getState().addImage(msgId, 'test.png', 'https://minio.example.com/test.png');

    const msg = useChatStore.getState().messages[msgId];
    expect(msg.images).toEqual({ 'test.png': 'https://minio.example.com/test.png' });
  });
});
