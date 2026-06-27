import { useEffect, useState } from 'react';
import { useChatStore } from '../store/chatStore';
import { useChatStream } from '../hooks/useChatStream';
import { MessageList } from './MessageList';
import { InputBox } from './InputBox';
import type { AgentInfo } from '../types/agent';

export function ChatContainer() {
  const { send, isSending } = useChatStream();
  const agentId = useChatStore((s) => s.agentId);
  const setAgentId = useChatStore((s) => s.setAgentId);
  const [agents, setAgents] = useState<AgentInfo[]>([]);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    fetch('/api/agents', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setAgents(data);
        } else if (data && Array.isArray(data.content)) {
          setAgents(data.content);
        }
      })
      .catch(() => {
        setAgents([]);
      });
  }, []);

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="border-b bg-white px-4 py-3 flex items-center gap-4 shrink-0">
        <h1 className="text-lg font-semibold text-gray-900">AI Chat</h1>
        <select
          value={agentId || ''}
          onChange={(e) => setAgentId(e.target.value)}
          className="border border-gray-300 rounded px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Default Agent</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.display_name || a.name}
            </option>
          ))}
        </select>
      </header>

      {/* Message list */}
      <MessageList />

      {/* Input */}
      <InputBox onSend={send} disabled={isSending} />
    </div>
  );
}

export default ChatContainer;
