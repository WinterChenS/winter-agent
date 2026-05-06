import React, { useState, useEffect, useRef } from 'react';
import { MessageList } from './components/MessageList';
import { ChatInput } from './components/ChatInput';
import { Sidebar } from './components/Sidebar';
import { useChat } from './hooks/useChat';
import { useSessions } from './hooks/useSessions';
import { Routes, Route, useNavigate, useParams } from 'react-router-dom';

function ChatInterface() {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const navigate = useNavigate();
  const { id: routeSessionId } = useParams();
  const isNewSessionRef = useRef(false);

  const {
    sessions,
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

  // 与路由同步状态
  useEffect(() => {
    if (routeSessionId) {
      if (isNewSessionRef.current) {
        // 如果是刚刚手动创建的新会话，本地已经是最新对话界面，直接跳过从服务器拉取空历史，防止覆盖刚才发送的消息
        isNewSessionRef.current = false;
      } else {
        loadHistory(routeSessionId);
      }
    } else {
      clearMessages();
    }
  }, [routeSessionId, loadHistory, clearMessages]);

  const handleSelectSession = (id: string) => {
    navigate(`/chat/${id}`);
  };

  const handleNewSession = () => {
    navigate('/');
  };

  const handleDeleteSession = (id: string) => {
    removeSession(id);
    if (routeSessionId === id) {
      navigate('/');
    }
  };

  const handleSendMessage = async (content: string) => {
    let currentSessionId = routeSessionId;
    
    if (!currentSessionId) {
      isNewSessionRef.current = true;
      currentSessionId = createSession(content.slice(0, 15) + (content.length > 15 ? '...' : ''));
      setConversationId(currentSessionId);
      // 利用 replace 防止新开对话破坏后退历史记录队列
      navigate(`/chat/${currentSessionId}`, { replace: true });
    } else if (messages.length === 0) {
      updateSessionTitle(currentSessionId, content.slice(0, 15) + (content.length > 15 ? '...' : ''));
    }
    
    await originalSendMessage(content);
  };

  return (
    <div className="flex h-screen bg-white">
      <Sidebar 
        sessions={sessions}
        activeSessionId={routeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
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
            {routeSessionId ? sessions.find(s => s.id === routeSessionId)?.title || 'AI Chat' : '新对话'}
          </h1>
          {messages.length > 0 && (
            <button
              onClick={handleNewSession}
              className="ml-auto text-sm text-gray-500 hover:text-gray-800 transition-colors"
            >
              清空/新对话
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

function App() {
  return (
    <Routes>
      <Route path="/" element={<ChatInterface />} />
      <Route path="/chat/:id" element={<ChatInterface />} />
    </Routes>
  );
}

export default App;
