import { useEffect, useRef, useState, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { Sidebar } from '../components/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { useSessions } from '../hooks/useSessions';
import { useChatStore } from '../features/ai-chat/store/chatStore';
import { useChatStream } from '../features/ai-chat/hooks/useChatStream';
import { useConversation } from '../features/ai-chat/hooks/useConversation';
import { MessageList } from '../features/ai-chat/components/MessageList';
import type { AgentInfo } from '../features/ai-chat/types/agent';
import { InputBox } from '../features/ai-chat/components/InputBox';
import { ChatContainer } from '../features/ai-chat/components/ChatContainer';

export function ChatInterface() {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const navigate = useNavigate();
  const { id: routeSessionId } = useParams();
  const isNewSessionRef = useRef(false);

  const { sessions, createSession, removeSession, updateSessionTitle } = useSessions();
  const { username, logout } = useAuth();
  const agentId = useChatStore(s => s.agentId);
  const setAgentId = useChatStore(s => s.setAgentId);
  const [agents, setAgents] = useState<AgentInfo[]>([]);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    fetch('/api/agents', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(res => res.json())
      .then(data => setAgents(Array.isArray(data) ? data : []))
      .catch(() => setAgents([]));
  }, []);
  const { send, isSending } = useChatStream();
  const { loadHistory } = useConversation();
  const messageOrder = useChatStore(s => s.messageOrder);
  const messagesMap = useChatStore(s => s.messages);
  const messages = useMemo(
    () => messageOrder.map(id => messagesMap[id]),
    [messageOrder, messagesMap],
  );
  const setConversationId = useChatStore(s => s.setConversationId);
  const clearMessages = useChatStore(s => s.clearMessages);

  // Route 与会话状态同步：切换 URL 时按会话加载历史
  useEffect(() => {
    if (routeSessionId) {
      if (isNewSessionRef.current) {
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
      navigate(`/chat/${currentSessionId}`, { replace: true });
    } else if (messages.length === 0) {
      updateSessionTitle(currentSessionId, content.slice(0, 15) + (content.length > 15 ? '...' : ''));
    }

    await send(content);
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
          <select
            value={agentId || ''}
            onChange={e => setAgentId(e.target.value)}
            className="ml-4 border border-gray-300 rounded px-2 py-1 text-sm text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Default Agent</option>
            {agents.map(a => (
              <option key={a.id} value={a.id}>
                {a.display_name || a.name}
              </option>
            ))}
          </select>
          <div className="ml-auto flex items-center gap-4">
            {messages.length > 0 && (
              <button
                onClick={handleNewSession}
                className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
              >
                清空/新对话
              </button>
            )}
            {username && (
              <span className="text-sm text-gray-400">{username}</span>
            )}
            <button
              onClick={() => { logout(); navigate('/login'); }}
              className="text-sm text-gray-400 hover:text-red-500 transition-colors flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              退出
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-hidden relative">
          <ChatContainer>
            <MessageList />
          </ChatContainer>
        </main>

        <footer className="bg-white py-4 shrink-0 shadow-[0_-1px_2px_rgba(0,0,0,0.05)] w-full">
          <ChatContainer>
            <InputBox onSend={handleSendMessage} disabled={isSending} />
            <p className="text-xs text-center text-gray-400 mt-2">AI 可能会产生错误信息，请核实重要内容。</p>
          </ChatContainer>
        </footer>
      </div>
    </div>
  );
}
