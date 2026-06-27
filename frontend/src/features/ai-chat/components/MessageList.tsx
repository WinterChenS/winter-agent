import { useRef, useState, useCallback, useMemo, useEffect } from 'react';
import { useChatStore } from '../store/chatStore';
import { MessageBubble } from './MessageBubble';

export function MessageList() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
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
    if (!scrollRef.current) return;
    const d =
      scrollRef.current.scrollHeight -
      scrollRef.current.scrollTop -
      scrollRef.current.clientHeight;
    setUserScrolledUp(d >= 64);
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
    <div className="h-full overflow-y-auto px-4 py-2" ref={scrollRef} onScroll={handleScroll}>
      {orderedMessages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
      {userScrolledUp && (
        <button
          onClick={() => {
            scrollToBottom(true);
            setUserScrolledUp(false);
          }}
          className="sticky bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 bg-white border border-gray-200 rounded-full shadow-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors z-10"
        >
          ↓ 回到底部
        </button>
      )}
    </div>
  );
}

export default MessageList;
