import React from 'react';
import { ChatMessage } from './ChatMessage';
import { Message } from '../types/chat';

interface MessageListProps {
  messages: Message[];
}

export const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  return (
    <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
      {messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full text-gray-500">
          <div className="text-6xl mb-4">🤖</div>
          <p className="text-xl font-medium">AI Chat V0.1</p>
          <p className="text-sm mt-2">开始与 AI 对话吧！</p>
        </div>
      ) : (
        <>
          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              role={message.role}
              content={message.content}
            />
          ))}
        </>
      )}
    </div>
  );
};
