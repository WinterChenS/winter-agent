import React, { useEffect, useRef } from 'react';
import { ChatMessage } from './ChatMessage';
import { Message } from '../types/chat';

interface MessageListProps {
  messages: Message[];
  isSending?: boolean;
}

export const MessageList: React.FC<MessageListProps> = ({ messages, isSending = false }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isSending]);

  const lastIndex = messages.length - 1;

  return (
    <div className="h-full overflow-y-auto p-4 bg-gray-50">
      {messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full text-gray-500">
          <div className="text-6xl mb-4">🤖</div>
          <p className="text-xl font-medium">AI Chat V0.2</p>
          <p className="text-sm mt-2">开始与 AI 对话吧！</p>
        </div>
      ) : (
        <>
          {messages.map((message, index) => (
            <ChatMessage
              key={message.id}
              role={message.role}
              content={message.content}
              isLoading={
                isSending &&
                index === lastIndex &&
                message.role === 'assistant' &&
                !message.content
              }
            />
          ))}
          <div ref={bottomRef} />
        </>
      )}
    </div>
  );
};
