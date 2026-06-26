import { useRef, useState, useCallback, useMemo, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useChatStore } from '../store/chatStore';
import { MessageBubble } from './MessageBubble';

export function MessageList() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const messageOrder = useChatStore((s) => s.messageOrder);
  const messages = useChatStore((s) => s.messages);

  const orderedMessages = useMemo(
    () => messageOrder.map((id) => messages[id]),
    [messageOrder, messages]
  );

  const virtualizer = useVirtualizer({
    count: orderedMessages.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 120,
    measureElement: (el) => el.getBoundingClientRect().height,
    overscan: 5,
  });

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setIsAtBottom(distanceFromBottom < 50);
  }, []);

  // Determine when to auto-scroll
  const msgCount = orderedMessages.length;
  const lastMsg = orderedMessages[msgCount - 1];
  const lastStreamingContentLen = lastMsg?.status === 'streaming' ? (lastMsg.content?.length ?? 0) : 0;

  useEffect(() => {
    if (isAtBottom && msgCount > 0) {
      const id = requestAnimationFrame(() => {
        virtualizer.scrollToIndex(msgCount - 1, { align: 'end' });
      });
      return () => cancelAnimationFrame(id);
    }
  }, [msgCount, lastStreamingContentLen, isAtBottom, virtualizer]);

  const scrollToBottom = useCallback(() => {
    const idx = orderedMessages.length - 1;
    if (idx >= 0) {
      virtualizer.scrollToIndex(idx, { align: 'end' });
    }
  }, [virtualizer, orderedMessages.length]);

  // If no messages, show empty state
  if (orderedMessages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        开始新的对话
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-hidden relative">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        style={{ overflow: 'auto', height: '100%' }}
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            position: 'relative',
          }}
        >
          {virtualizer.getVirtualItems().map((virtualItem) => {
            const msg = orderedMessages[virtualItem.index];
            if (!msg) return null;
            return (
              <div
                key={virtualItem.key}
                data-index={virtualItem.index}
                ref={virtualizer.measureElement}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualItem.start}px)`,
                }}
              >
                <MessageBubble message={msg} />
              </div>
            );
          })}
        </div>
      </div>
      {!isAtBottom && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 bg-white border border-gray-200 rounded-full shadow-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors z-10"
        >
          ↓ 回到底部
        </button>
      )}
    </div>
  );
}
