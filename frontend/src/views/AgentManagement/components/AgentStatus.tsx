interface AgentStatusProps {
  enabled: boolean;
  onToggle: () => void;
}

export function AgentStatus({ enabled, onToggle }: AgentStatusProps) {
  return (
    <button
      onClick={onToggle}
      className={`
        inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full
        transition-colors
        ${enabled
          ? 'bg-green-100 text-green-700 hover:bg-green-200'
          : 'bg-red-100 text-red-700 hover:bg-red-200'
        }
      `}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          enabled ? 'bg-green-500' : 'bg-red-500'
        }`}
      />
      {enabled ? '启用' : '禁用'}
    </button>
  );
}
