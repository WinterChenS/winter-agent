import type { AgentInfo } from '../../../features/ai-chat/types/agent';
import { AgentStatus } from './AgentStatus';

interface AgentCardProps {
  agent: AgentInfo;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  onToggle: (id: string, enabled: boolean) => void;
  onClone: (id: string) => void;
}

export function AgentCard({ agent, onEdit, onDelete, onToggle, onClone }: AgentCardProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{agent.icon || '🤖'}</span>
          <div>
            <h3 className="font-semibold text-gray-900">{agent.display_name}</h3>
            <span className="text-xs text-gray-500">{agent.name}</span>
          </div>
        </div>
        <AgentStatus enabled={agent.enabled} onToggle={() => onToggle(agent.id, !agent.enabled)} />
      </div>

      {agent.description && (
        <p className="text-sm text-gray-600 mb-3 line-clamp-2">{agent.description}</p>
      )}

      {agent.tags && agent.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {agent.tags.map(tag => (
            <span key={tag} className="px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-600">
              {tag}
            </span>
          ))}
        </div>
      )}

      {agent.agent_type && (
        <div className="mb-3">
          <span className="px-2 py-0.5 text-xs rounded bg-blue-100 text-blue-700">
            {agent.agent_type}
          </span>
        </div>
      )}

      {agent.tools && agent.tools.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {agent.tools.map(tool => (
            <span key={tool} className="px-2 py-0.5 text-xs rounded bg-purple-100 text-purple-600">
              {tool}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
        <button
          onClick={() => onEdit(agent.id)}
          aria-label="编辑"
          className="px-3 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded transition-colors"
        >
          编辑
        </button>
        <button
          onClick={() => onClone(agent.id)}
          aria-label="克隆"
          className="px-3 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded transition-colors"
        >
          克隆
        </button>
        <button
          onClick={() => onDelete(agent.id)}
          aria-label="删除"
          className="px-3 py-1 text-xs text-red-600 hover:bg-red-50 rounded transition-colors ml-auto"
        >
          删除
        </button>
      </div>
    </div>
  );
}
