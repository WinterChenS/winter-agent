import { useChatStore } from '../store/chatStore';

const STATUS_LABELS: Record<string, string> = {
  thinking: 'Thinking...',
  calling_tool: 'Calling tool...',
  generating: 'Generating...',
};

export function AgentStatusIndicator() {
  const agentStatus = useChatStore(s => s.agentStatus);
  const activeAgent = useChatStore(s => s.activeAgent);
  const activeAgentDisplay = useChatStore(s => s.activeAgentDisplay);

  if (agentStatus === 'idle') return null;

  const displayName = activeAgentDisplay || activeAgent || 'Agent';
  const statusLabel = STATUS_LABELS[agentStatus] || agentStatus;

  return (
    <div className="agent-status-indicator flex items-center gap-1.5 text-xs text-gray-400 ml-3">
      <span className="agent-status-icon inline-block w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
      <span className="font-medium">{displayName}</span>
      <span>{statusLabel}</span>
    </div>
  );
}
