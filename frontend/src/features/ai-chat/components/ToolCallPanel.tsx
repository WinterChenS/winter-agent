import { useState } from 'react';
import type { ToolCall } from '../types/message';

interface ToolCallPanelProps {
  toolCalls: ToolCall[];
}

function ToolCallItem({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);

  const isRunning = toolCall.status === 'running' || toolCall.status === 'pending';

  const statusIcon = isRunning ? (
    <span className="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
  ) : toolCall.status === 'done' ? (
    <span className="text-green-500 font-bold">&#x2713;</span>
  ) : (
    <span className="text-red-500 font-bold">&#x2717;</span>
  );

  const showExpand =
    (toolCall.status === 'done' || toolCall.status === 'failed') &&
    toolCall.result !== undefined;

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm">
      <div className="flex items-center gap-2">
        {statusIcon}
        <span className="font-mono font-medium text-gray-800">{toolCall.name}</span>
        {showExpand && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="ml-auto text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            {expanded ? '收起' : '查看详情'}
          </button>
        )}
      </div>
      {expanded && toolCall.result !== undefined && (
        <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-x-auto max-h-60 overflow-y-auto">
          {typeof toolCall.result === 'string'
            ? toolCall.result
            : JSON.stringify(toolCall.result, null, 2)}
        </pre>
      )}
    </div>
  );
}

export function ToolCallPanel({ toolCalls }: ToolCallPanelProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="space-y-2 mb-3">
      {toolCalls.map((tc) => (
        <ToolCallItem key={tc.id} toolCall={tc} />
      ))}
    </div>
  );
}
