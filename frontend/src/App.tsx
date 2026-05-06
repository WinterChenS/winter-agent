import React, { useState, useEffect } from 'react';
import { MessageList } from './components/MessageList';
import { ChatInput } from './components/ChatInput';
import { Sidebar } from './components/Sidebar';
import { useChat } from './hooks/useChat';
import { useSessions } from './hooks/useSessions';

function App() {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const {
    sessions,
    activeSessionId,
    setActiveSessionId,
    createSession,
    removeSession,
    updateSessionTitle
  } = useSessions();

  const {
    messages,
    isSending,
    messagesEndRef,
    sendMessage: originalSendMessage,
    clearMessages,
    loadHistory,
    setConversationId
  } = useChat();

  // 当外部 session 切换时重新加载内容
  useEffect(() => {
    if (activeSessionId) {
      loadHistory(activeSessionId);
    } else {
      clearMessages();
    }
  }, [activeSessionId, loadHistory, clearMessages]);

  const handleSendMessage = async (content: string) => {
    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      currentSessionId = createSession(content.slice(0, 15) + (content.length > 15 ? '...' : ''));
      setConversationId(currentSessionId);
    } else if (messages.length === 0) {
      updateSessionTitle(currentSessionId, content.slice(0, 15) + (content.length > 15 ? '...' : ''));
    }
    
    await originalSendMessage(content);
  };

  return (
    <div className="flex h-screen bg-white">
      <Sidebar 
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={setActiveSessionId}
        onNewSession={() => setActiveSessionId(undefined)}
        onDeleteSession={removeSession}
        isMobileOpen={isMobileSidebarOpen}
        setMobileOpen={setIsMobileSidebarOpen}
      />
      
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center shrink-0">
          <button
            onClick={() => setIsMobileSidebarOpen(true)}
            className="md:hidden mr-4 text-gray-500 hover:text-gray-700"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <h1 className="text-xl font-semibold text-gray-800">
            {activeSessionId ? sessions.find(s => s.id === activeSessionId)?.title || 'AI Chat' : '新对话'}
          </h1>
          {messages.length > 0 && (
            <button
              onClick={() => setActiveSessionId(undefined)}
              className="ml-auto text-sm text-gray-500 hover:text-gray-800 transition-colors"
            >
              清空对话
            </button>
          )}
        </header>

        <main className="flex-1 overflow-hidden relative">
          <MessageList 
            messages={messages} 
            messagesEndRef={messagesEndRef} 
          />
        </main>

        <footer className="bg-white px-4 py-4 shrink-0 shadow-[0_-1px_2px_rgba(0,0,0,0.05)] w-full">
          <div className="max-w-4xl mx-auto w-full">
            <ChatInput 
              onSend={handleSendMessage} 
              disabled={isSending} 
            />
            <p className="text-xs text-center text-gray-400 mt-2">
              AI 可能会产生错误信息，请核实重要内容。
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default App;
