import React, { useState, useMemo } from 'react';
import type { ToolCall } from '../types/message';

interface ToolCallPanelProps {
  toolCalls: ToolCall[];
}

function aggregateStatus(toolCalls: ToolCall[]): 'done' | 'running' | 'failed' {
  let hasRunning = false;
  let hasFailed = false;
  for (const tc of toolCalls) {
    if (tc.status === 'running' || tc.status === 'pending') hasRunning = true;
    else if (tc.status === 'failed') hasFailed = true;
  }
  if (hasFailed) return 'failed';
  if (hasRunning) return 'running';
  return 'done';
}

function AggregateIcon({ status }: { status: 'done' | 'running' | 'failed' }) {
  if (status === 'running') {
    return (
      <span className="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    );
  }
  if (status === 'failed') {
    return <span className="text-red-500 font-bold">✗</span>;
  }
  return <span className="text-green-500 font-bold">✓</span>;
}

const ToolCallItem = React.memo(function ToolCallItem({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);

  const isRunning = toolCall.status === 'running' || toolCall.status === 'pending';

  const statusIcon = isRunning ? (
    <span className="inline-block w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
  ) : toolCall.status === 'done' ? (
    <span className="text-green-500">✓</span>
  ) : (
    <span className="text-red-500">✗</span>
  );

  const statusText = isRunning
    ? 'executing...'
    : toolCall.status === 'done'
      ? 'completed'
      : 'failed';

  const showExpand =
    (toolCall.status === 'done' || toolCall.status === 'failed') &&
    toolCall.result !== undefined;

  return (
    <div className="flex items-start gap-2 py-1.5 text-sm">
      <span className="mt-0.5 shrink-0">{statusIcon}</span>
      <span className="font-mono text-gray-700 min-w-[80px]">{toolCall.name}</span>
      <span className={`text-xs mt-0.5 ${
        isRunning ? 'text-blue-500' : toolCall.status === 'done' ? 'text-green-600' : 'text-red-500'
      }`}>
        {statusText}
      </span>
      {showExpand && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="ml-auto text-xs text-gray-400 hover:text-gray-600 transition-colors shrink-0"
        >
          {expanded ? '收起' : '查看详情'}
        </button>
      )}
      {expanded && toolCall.result !== undefined && (
        <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-x-auto max-h-60 overflow-y-auto col-span-full">
          {typeof toolCall.result === 'string'
            ? toolCall.result
            : JSON.stringify(toolCall.result, null, 2)}
        </pre>
      )}
    </div>
  );
});

export function ToolCallPanel({ toolCalls }: ToolCallPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const tools = toolCalls ?? [];

  if (tools.length === 0) return null;

  const status = useMemo(() => aggregateStatus(tools), [tools]);
  const defaultCollapsed = tools.length > 1 && status === 'done';

  const effectiveCollapsed = collapsed || defaultCollapsed;

  return (
    <div className="border border-gray-200 rounded-lg mb-3 text-sm overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <AggregateIcon status={status} />
        <span className="font-medium text-gray-700">
          {tools.length} {tools.length > 1 ? 'tools' : 'tool'}
        </span>
        {tools.length > 1 && (
          <span className="ml-auto text-gray-400 text-xs transition-transform">
            {collapsed ? '▶' : '▼'}
          </span>
        )}
      </button>
      {/* Body */}
      {!collapsed && (
        <div className="px-3 py-1.5 divide-y divide-gray-100">
          {tools.map((tc) => (
            <ToolCallItem key={tc.id} toolCall={tc} />
          ))}
        </div>
      )}
    </div>
  );
}
