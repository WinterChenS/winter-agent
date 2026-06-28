import { useRef, useState, useCallback, useMemo, useEffect } from 'react';
import { useChatStore } from '../store/chatStore';
import { MessageBubble } from './MessageBubble';

export function MessageList() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const [contentOverflows, setContentOverflows] = useState(false);
  const isSending = useChatStore((s) => s.isSending);

  const messageOrder = useChatStore((s) => s.messageOrder);
  const messages = useChatStore((s) => s.messages);

  const orderedMessages = useMemo(
    () => messageOrder.map((id) => messages[id]).filter(Boolean),
    [messageOrder, messages]
  );

  const isAtBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return true;
    const d = el.scrollHeight - el.scrollTop - el.clientHeight;
    return d < 64;
  }, []);

  const scrollToBottom = useCallback((smooth = true) => {
    bottomRef.current?.scrollIntoView({
      behavior: smooth ? 'smooth' : 'instant',
    });
  }, []);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const d = el.scrollHeight - el.scrollTop - el.clientHeight;
    const overflows = el.scrollHeight > el.clientHeight + 10;
    setContentOverflows(overflows);
    setUserScrolledUp(overflows && d >= 64);
  }, []);

  // Auto-scroll: scroll to bottom when new messages arrive and user is at bottom
  useEffect(() => {
    if (!userScrolledUp && orderedMessages.length > 0) {
      scrollToBottom(isSending ? false : true);
    }
  }, [orderedMessages.length, userScrolledUp, scrollToBottom, isSending]);

  // During streaming: auto-scroll if user hasn't scrolled up
  const lastMsg = orderedMessages[orderedMessages.length - 1];
  const streamingContent = lastMsg?.status === 'streaming' ? lastMsg.content : '';

  useEffect(() => {
    if (!userScrolledUp && streamingContent) {
      scrollToBottom(false);
    }
  }, [streamingContent, userScrolledUp, scrollToBottom]);

  if (orderedMessages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        开始新的对话
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto py-2" ref={scrollRef} onScroll={handleScroll}>
      {orderedMessages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
      {userScrolledUp && contentOverflows && (
        <button
          onClick={() => {
            scrollToBottom(true);
            setUserScrolledUp(false);
          }}
          className="fixed bottom-28 right-6 w-9 h-9 flex items-center justify-center bg-white border border-gray-200 rounded-full shadow-lg text-gray-500 hover:text-gray-700 hover:bg-gray-50 transition-colors z-50"
          aria-label="回到底部"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </button>
      )}
    </div>
  );
}

export default MessageList;
