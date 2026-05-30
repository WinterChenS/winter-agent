import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';
import { ChartRenderer } from './ChartRenderer';

interface ChatMessageProps {
  role: 'user' | 'assistant' | 'tool_summary' | 'agent_step' | 'chart' | 'thinking';
  content: string;
  isLoading?: boolean;
  toolSteps?: Array<{
    tool: string;
    input: string;
    status: 'completed' | 'error' | 'running';
    elapsed_ms: number;
    error?: string;
  }>;
  guardReason?: {
    node?: string;
    code?: string;
    message?: string;
    timestamp?: number;
    extra?: Record<string, unknown>;
  };
  chartData?: import('../types/chat').ChartSpecData;
  chartDatas?: import('../types/chat').ChartSpecData[];
}

type ToolStepKind = 'start' | 'result';

interface ToolStep {
  raw: string;
  toolName: string;
  kind: ToolStepKind;
}

type SummaryToolStep = NonNullable<ChatMessageProps['toolSteps']>[number];

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
  if (normalized.includes('__thought__')) return '💭';
  if (normalized.includes('search')) return '🔎';
  if (normalized.includes('browser')) return '🌐';
  if (normalized.includes('python')) return '🐍';
  if (normalized.includes('echo')) return '🗣️';
  return '🛠️';
}

function getGuardReasonLabel(code?: string): string {
  switch (code) {
    case 'MAX_CONSECUTIVE_SEARCH_REACHED':
      return '已触发连续检索上限，转为直接总结';
    case 'SEARCH_RESULTS_ALREADY_AVAILABLE':
      return '已有检索结果，停止重复检索';
    case 'DUPLICATE_TOOL_CALL_BLOCKED':
      return '检测到重复工具调用，已自动收敛';
    case 'MAX_ITERATIONS_REACHED':
      return '达到本轮工具调用上限，停止继续调用';
    case 'TIME_REPEAT_AUTOSWITCH_SEARCH':
      return '检测到重复时间查询，已自动改为检索';
    case 'TIME_REPEAT_FINALIZED':
      return '检测到重复时间查询，已直接给出结果';
    default:
      return 'Agent 策略触发';
  }
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
    <div className="relative group my-3">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity z-10 border border-gray-300"
      >
        {copied ? '已复制' : '复制'}
      </button>
      <pre className="!mt-0 !mb-0 bg-gray-50 rounded-lg border border-gray-200" {...props}>
        {children}
      </pre>
    </div>
  );
};

export const ChatMessage: React.FC<ChatMessageProps> = ({
  role,
  content,
  isLoading = false,
  toolSteps = [],
  guardReason,
  chartData,
  chartDatas,
}) => {
  // Normalize: support both single chartData (legacy) and chartDatas (multi-chart)
  const allCharts = chartDatas || (chartData ? [chartData] : []);
  // Chart message (backward compatibility)
  if (role === 'chart' && chartData) {
    return (
      <div className="flex justify-start mb-4">
        <div className="max-w-[85%] rounded-2xl px-4 py-3 bg-white border border-gray-200 shadow-sm">
          <ChartRenderer chartData={chartData} />
          {chartData.description && (
            <p className="text-sm text-gray-600 mt-3">{chartData.description}</p>
          )}
        </div>
      </div>
    );
  }

  // Thinking pane: real-time agent process display
  if (role === 'thinking') {
    return <ThinkingPane toolSteps={toolSteps || []} isDone={content === 'done'} />;
  }

  const isUser = role === 'user';
  const isToolSummary = role === 'tool_summary';
  const isAgentStep = role === 'agent_step';

  const { answer } = useMemo<{ toolSteps: ToolStep[]; answer: string }>(() => {
    if (isUser || isToolSummary || isAgentStep) {
      return { toolSteps: [], answer: content };
    }
    return splitToolLines(content);
  }, [isUser, isToolSummary, isAgentStep, content]);

  const [showThinking, setShowThinking] = useState(true);
  const summarySteps: SummaryToolStep[] = toolSteps;

  // Build thinking steps from summary tool data (tool_summary SSE event)
  const hasThinking = summarySteps.length > 0;

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-blue-500 text-white'
            : isToolSummary
              ? 'bg-purple-50 text-gray-800 border border-purple-200'
              : isAgentStep
                ? 'bg-amber-50 text-gray-800 border border-amber-200'
                : 'bg-gray-100 text-gray-800'
        }`}
      >
        {/* ============ User Message ============ */}
        {isUser ? (
          <div className="whitespace-pre-wrap">{content}</div>
        ) : isAgentStep ? (
          /* ============ Agent Step ============ */
          <div className="space-y-2 text-sm">
            <div className="font-semibold text-amber-900">⚙️ {getGuardReasonLabel(guardReason?.code)}</div>
            <div className="text-amber-900">{guardReason?.message || content}</div>
            {guardReason?.code && (
              <div className="text-xs text-amber-800">
                <span className="opacity-70">code:</span> <span className="font-mono">{guardReason.code}</span>
              </div>
            )}
            {guardReason?.extra && Object.keys(guardReason.extra).length > 0 && (
              <pre className="mt-2 overflow-x-auto rounded bg-amber-100 p-2 text-xs text-amber-900">
                {JSON.stringify(guardReason.extra, null, 2)}
              </pre>
            )}
          </div>
        ) : isToolSummary ? (
          /* ============ Tool Summary (separate message) ============ */
          <div>
            <div className="mb-3">
              <button
                onClick={() => setShowThinking(prev => !prev)}
                className="flex items-center justify-between text-sm font-semibold text-purple-900 hover:text-purple-700 w-full"
              >
                <span>🔍 Agent 工具执行步骤 ({summarySteps.length})</span>
                <span className="text-xs">{showThinking ? '▼' : '▶'}</span>
              </button>
            </div>

            {showThinking && summarySteps.length > 0 && (
              <div className="space-y-3">
                {summarySteps.map((rawStep, idx) => {
                  const step = rawStep as SummaryToolStep;
                  return (
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
                  );
                })}
              </div>
            )}
          </div>
        ) : isLoading && !content ? (
          /* ============ Loading ============ */
          <div className="flex items-center gap-2 text-gray-500">
            <span className="inline-flex gap-1">
              <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400 [animation-delay:0ms]" />
              <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400 [animation-delay:150ms]" />
              <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400 [animation-delay:300ms]" />
            </span>
            <span className="text-sm">AI 正在思考...</span>
          </div>
        ) : (
          /* ============ Assistant Answer ============ */
          <>
            {/* Thinking process: collapsible, shows tool execution steps */}
            {hasThinking && (
              <div className="mb-3">
                <button
                  onClick={() => setShowThinking(prev => !prev)}
                  className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-700 transition-colors"
                >
                  <span className="inline-flex items-center gap-1">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    思考过程
                  </span>
                  <span className="text-xs">{showThinking ? '收起 ▲' : '展开 ▼'}</span>
                </button>

                {showThinking && (
                  <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-gray-200 bg-white">
                    <div className="p-2 space-y-1.5">
                      {summarySteps.map((step, idx) => (
                        <div key={`think-${idx}`} className="flex items-center gap-2 text-xs text-gray-600">
                          <span>{getToolIcon(step.tool)}</span>
                          <span className="font-medium text-gray-700">{step.tool}</span>
                          {step.input && (
                            <span className="text-gray-400 truncate max-w-[200px]">{step.input}</span>
                          )}
                          <span className="text-gray-400">·</span>
                          <span className={step.status === 'completed' ? 'text-green-600' : 'text-red-600'}>
                            {step.status === 'completed' ? '完成' : '失败'}
                          </span>
                          {step.elapsed_ms > 0 && (
                            <span className="text-gray-400 ml-auto">{step.elapsed_ms}ms</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Main answer text */}
            {answer ? (
              <div className="prose prose-sm max-w-none prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-table:text-sm">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeHighlight]}
                  components={{
                    pre: PreBlock,
                    blockquote({ children }) {
                      return (
                        <blockquote className="border-l-4 border-blue-400 bg-blue-50 pl-4 pr-2 py-1.5 my-2 rounded-r-lg text-gray-700 not-italic">
                          {children}
                        </blockquote>
                      );
                    },
                    code({ className, children, ...props }) {
                      const isInline = !className;
                      if (isInline) {
                        return (
                          <code className="bg-gray-200 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
                            {children}
                          </code>
                        );
                      }
                      return (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      );
                    },
                    table({ children }) {
                      return (
                        <div className="overflow-x-auto my-2">
                          <table className="min-w-full border-collapse border border-gray-300 text-sm">
                            {children}
                          </table>
                        </div>
                      );
                    },
                    thead({ children }) {
                      return <thead className="bg-gray-100">{children}</thead>;
                    },
                    th({ children }) {
                      return <th className="border border-gray-300 px-3 py-1.5 text-left font-semibold">{children}</th>;
                    },
                    td({ children }) {
                      return <td className="border border-gray-300 px-3 py-1.5">{children}</td>;
                    },
                  }}
                >
                  {answer}
                </ReactMarkdown>
              </div>
            ) : null}

            {/* Charts: rendered INSIDE the assistant bubble, below the text */}
            {allCharts.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-200 space-y-4">
                {allCharts.map((cd, idx) => (
                  <div key={cd.id || idx}>
                    {allCharts.length > 1 && (
                      <p className="text-xs font-medium text-gray-500 mb-1">
                        图表 {idx + 1}: {cd.title}
                      </p>
                    )}
                    <ChartRenderer chartData={cd} />
                    {cd.description && !allCharts[1] && (
                      <p className="text-xs text-gray-500 mt-2">{cd.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// ThinkingPane: real-time agent process display (Claude Code-style)
// ────────────────────────────────────────────────────────────────────────────
const ThinkingPane: React.FC<{
  toolSteps: Array<{ tool: string; input: string; status: string; elapsed_ms?: number; error?: string }>;
  isDone: boolean;
}> = ({ toolSteps, isDone }) => {
  const [expanded, setExpanded] = useState(!isDone);
  const allDone = toolSteps.every(s => s.status !== 'running');

  React.useEffect(() => {
    if (allDone) {
      const timer = setTimeout(() => setExpanded(false), 1000);
      return () => clearTimeout(timer);
    }
  }, [allDone]);

  const runningCount = toolSteps.filter(s => s.status === 'running').length;
  const title = runningCount > 0
    ? `正在思考... (${runningCount} 个工具运行中)`
    : `已完成 ${toolSteps.length} 个步骤`;

  return (
    <div className="flex justify-start mb-1">
      <div className="max-w-[85%] rounded-xl overflow-hidden border border-blue-100 bg-blue-50/50 min-w-[280px]">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-gray-500 hover:bg-blue-100/50 transition-colors"
        >
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${allDone ? 'bg-green-400' : 'bg-blue-400 animate-pulse'}`} />
          <span className="font-medium text-gray-700">{title}</span>
          <span className="ml-auto text-gray-400">{expanded ? '收起 ▲' : '展开 ▼'}</span>
        </button>

        {expanded && (
          <div className="px-3 pb-2 max-h-60 overflow-y-auto">
            <div className="space-y-0.5 border-l-2 border-blue-200 pl-2">
              {toolSteps.map((step, idx) => (
                <div key={idx} className="flex items-center gap-2 text-xs py-0.5">
                  <span className="text-sm flex-shrink-0">{getToolIcon(step.tool)}</span>
                  <span className="font-medium text-gray-700 flex-shrink-0">{step.tool}</span>
                  {step.input && (
                    <span className="text-gray-400 truncate" title={step.input}>
                      {step.input.length > 50 ? step.input.slice(0, 50) + '...' : step.input}
                    </span>
                  )}
                  <span className="ml-auto flex items-center gap-1 flex-shrink-0">
                    {step.status === 'running' ? (
                      <span className="flex items-center gap-1 text-blue-500">
                        <span className="inline-block w-2.5 h-2.5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                      </span>
                    ) : step.status === 'error' ? (
                      <span className="text-red-500 text-xs" title={step.error}>✗</span>
                    ) : (
                      <span className="text-green-600 text-xs flex items-center gap-0.5">
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                        </svg>
                        {step.elapsed_ms ? `${(step.elapsed_ms / 1000).toFixed(1)}s` : ''}
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
