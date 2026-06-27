import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface ReasoningPanelProps {
  reasoning: string;
}

export function ReasoningPanel({ reasoning }: ReasoningPanelProps) {
  const [collapsed, setCollapsed] = useState(true);

  return (
    <div className="mb-3 bg-amber-50 border border-amber-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-amber-800 hover:bg-amber-100 transition-colors"
      >
        <span className="transform transition-transform duration-200 inline-block">
          {collapsed ? '▶' : '▼'}
        </span>
        <span>💭 思考过程</span>
      </button>
      {!collapsed && (
        <div className="px-3 py-2 text-sm text-amber-900 border-t border-amber-200 prose prose-amber max-w-none">
          <ReactMarkdown>{reasoning}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
