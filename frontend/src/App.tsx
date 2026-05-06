import React from 'react';
import { MessageList } from './components/MessageList';
import { ChatInput } from './components/ChatInput';
import { useChat } from './hooks/useChat';

const App: React.FC = () => {
  const {
    messages,
    isSending,
    messagesEndRef,
    sendMessage,
    clearMessages,
  } = useChat();

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="text-2xl">🤖</div>
          <div>
            <h1 className="text-lg font-semibold text-gray-800">AI Chat</h1>
            <p className="text-xs text-gray-500">V0.1 - 智能对话助手</p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearMessages}
            className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
          >
            清空对话
          </button>
        )}
      </header>

      {/* Message List */}
      <MessageList messages={messages} />
      <div ref={messagesEndRef} />

      {/* Input Area */}
      <ChatInput onSend={sendMessage} disabled={isSending} />
    </div>
  );
};

export default App;
