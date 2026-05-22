import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';

interface ChatMessageProps {
  role: 'user' | 'assistant' | 'tool_summary';
  content: string;
  isLoading?: boolean;
  toolSteps?: Array<{
    tool: string;
    input: string;
    status: 'completed' | 'error';
    elapsed_ms: number;
    error?: string;
  }>;
}

type ToolStepKind = 'start' | 'result';

interface ToolStep {
  raw: string;
  toolName: string;
  kind: ToolStepKind;
}

const TOOL_LINE_PREFIXES = ['🛠️ 正在调用工具：', '工具 `'];

function parseActionJsonLine(line: string): ToolStep | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) {
    return null;
  }

  try {
    const parsed = JSON.parse(trimmed) as { action?: string; tool?: string; query?: string };
    const action = (parsed.action || '').trim();
    const toolName = action === 'tool' ? (parsed.tool || '').trim() : action;
    if (!toolName) {
      return null;
    }

    const queryPart = parsed.query ? `（query: ${parsed.query}）` : '';
    return {
      raw: `🛠️ 正在调用工具：${toolName}... ${queryPart}`.trim(),
      toolName,
      kind: 'start',
    };
  } catch {
    return null;
  }
}

function parseToolName(line: string): string {
  const startPrefix = '🛠️ 正在调用工具：';
  if (line.startsWith(startPrefix)) {
    return line.replace(startPrefix, '').replace(/\.\.\.$/, '').trim() || 'unknown';
  }

  const match = line.match(/^工具\s+`([^`]+)`/);
  if (match?.[1]) {
    return match[1];
  }

  return 'unknown';
}

function getToolIcon(toolName: string): string {
  const normalized = toolName.toLowerCase();
  if (normalized.includes('search')) return '🔎';
  if (normalized.includes('python')) return '🐍';
  if (normalized.includes('file')) return '📄';
  if (normalized.includes('echo')) return '🗣️';
  return '🛠️';
}

function splitToolLines(content: string): { toolSteps: ToolStep[]; answer: string } {
  if (!content) {
    return { toolSteps: [], answer: '' };
  }

  const toolSteps: ToolStep[] = [];
  const normalLines: string[] = [];

  for (const line of content.split('\n')) {
    const trimmed = line.trim();

    const actionStep = parseActionJsonLine(trimmed);
    if (actionStep) {
      toolSteps.push(actionStep);
      continue;
    }

    if (TOOL_LINE_PREFIXES.some(prefix => trimmed.startsWith(prefix))) {
      const kind: ToolStepKind = trimmed.startsWith('🛠️') ? 'start' : 'result';
      toolSteps.push({
        raw: trimmed,
        toolName: parseToolName(trimmed),
        kind,
      });
    } else {
      normalLines.push(line);
    }
  }

  return {
    toolSteps,
    answer: normalLines.join('\n').trim(),
  };
}

const PreBlock = ({ children, ...props }: any) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = (e: React.MouseEvent<HTMLButtonElement>) => {
    const codeNode = e.currentTarget.parentElement?.querySelector('code');
    if (codeNode) {
      navigator.clipboard.writeText(codeNode.textContent || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="relative group my-4">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity z-10 border border-gray-300"
      >
        {copied ? '已复制' : '复制'}
      </button>
      <pre className="!my-0" {...props}>
        {children}
      </pre>
    </div>
  );
};

export const ChatMessage: React.FC<ChatMessageProps> = ({ role, content, isLoading = false, toolSteps = [] }) => {
  const isUser = role === 'user';
  const isToolSummary = role === 'tool_summary';

  const { toolSteps: extractedSteps, answer } = useMemo(() => {
    if (isUser || isToolSummary) {
      return { toolSteps: [], answer: content };
    }
    return splitToolLines(content);
  }, [isUser, isToolSummary, content]);

  const [showToolSteps, setShowToolSteps] = useState(false);

  // 对于 tool_summary 消息，直接使用传入的 toolSteps，否则使用从 content 中解析的
  const displaySteps = isToolSummary ? toolSteps : extractedSteps;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser ? 'bg-blue-500 text-white' : isToolSummary ? 'bg-purple-50 text-gray-800 border border-purple-200' : 'bg-gray-100 text-gray-800'
        }`}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{content}</div>
        ) : isToolSummary ? (
          // 工具摘要消息：完整分离的工具步骤展示
          <div>
            <div className="mb-3">
              <button
                onClick={() => setShowToolSteps(prev => !prev)}
                className="flex items-center justify-between text-sm font-semibold text-purple-900 hover:text-purple-700 w-full"
              >
                <span>🔍 Agent 工具执行步骤 ({displaySteps.length})</span>
                <span className="text-xs">{showToolSteps ? '▼' : '▶'}</span>
              </button>
            </div>

            {showToolSteps && displaySteps.length > 0 && (
              <div className="space-y-3">
                {displaySteps.map((step, idx) => (
                  <div
                    key={`step-${idx}`}
                    className={`rounded border px-3 py-2 text-sm ${
                      step.status === 'completed'
                        ? 'border-green-200 bg-green-50 text-green-900'
                        : 'border-red-200 bg-red-50 text-red-900'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">{getToolIcon(step.tool)}</span>
                      <span className="font-semibold">{step.tool}</span>
                      <span className="text-xs opacity-70">
                        {step.status === 'completed' ? '✓ 成功' : '✗ 失败'}
                      </span>
                      {step.elapsed_ms > 0 && (
                        <span className="text-xs opacity-60 ml-auto">{step.elapsed_ms}ms</span>
                      )}
                    </div>
                    {step.input && (
                      <div className="text-xs opacity-80 mt-1 break-words">
                        <span className="opacity-60">输入：</span>{step.input}
                      </div>
                    )}
                    {step.error && (
                      <div className="text-xs opacity-80 mt-1 break-words font-mono">
                        <span className="opacity-60">错误：</span>{step.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : isLoading && !content ? (
          <div className="flex items-center gap-2 text-gray-500">
            <span className="inline-flex gap-1">
              <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400 [animation-delay:0ms]" />
              <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400 [animation-delay:150ms]" />
              <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400 [animation-delay:300ms]" />
            </span>
            <span className="text-sm">AI 正在思考...</span>
          </div>
        ) : (
          <>
            {displaySteps.length > 0 && (
              <div className="mb-3 rounded-lg border border-blue-200 bg-blue-50">
                <button
                  onClick={() => setShowToolSteps(prev => !prev)}
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm text-blue-900 hover:bg-blue-100"
                >
                  <span>Agent 执行过程（{displaySteps.length} 步）</span>
                  <span>{showToolSteps ? '收起 ▲' : '展开 ▼'}</span>
                </button>

                {showToolSteps && (
                  <div className="px-3 pb-3">
                    <div className="space-y-2 border-l-2 border-blue-200 pl-3">
                      {displaySteps.map((step, idx) => (
                        <div key={`${step.raw || step.tool}-${idx}`} className="relative text-sm text-blue-800">
                          <span className="absolute -left-[1.12rem] top-1 inline-block h-2 w-2 rounded-full bg-blue-400" />
                          <span className="mr-2">{getToolIcon(step.toolName || step.tool)}</span>
                          <span className="font-medium">{step.toolName || step.tool}</span>
                          <span className="mx-2 text-blue-500">·</span>
                          <span>{step.kind === 'start' ? '开始执行' : '执行完成'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {answer ? (
              <div className="prose prose-sm max-w-none prose-pre:bg-white prose-pre:text-gray-800">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeHighlight]}
                  components={{
                    pre: PreBlock,
                    code({ className, children, ...props }) {
                      return (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {answer}
                </ReactMarkdown>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
};
