import type { Message } from '../types/message';
import { ReasoningPanel } from './ReasoningPanel';
import { ToolCallPanel } from './ToolCallPanel';
import { MarkdownRenderer } from './MarkdownRenderer';
import { StreamingRenderer } from './StreamingRenderer';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isStreaming = message.status === 'streaming';

  // Strip [CHART:n] markers from content — rendered separately
  const cleanContent = message.content.replace(/\[CHART:\d+\]/g, '').trim();

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 px-4`}>
      <div
        className={`max-w-[80%] rounded-lg p-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-white border border-gray-200 text-gray-900'
        }`}
      >
        {!isUser && message.agentId && (
          <span className="block text-xs text-gray-400 mb-1">
            Agent: {message.agentId}
          </span>
        )}

        {/* Assistant renderings */}
        {!isUser && message.reasoning && (
          <ReasoningPanel reasoning={message.reasoning} />
        )}
        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <ToolCallPanel toolCalls={message.toolCalls} />
        )}

        {/* Content */}
        {isUser ? (
          <div className="whitespace-pre-wrap">{cleanContent}</div>
        ) : (
          <StreamingRenderer isStreaming={isStreaming}>
            <MarkdownRenderer content={cleanContent} />
          </StreamingRenderer>
        )}

        {/* Charts (from chart SSE events) */}
        {!isUser && message.charts && message.charts.length > 0 && (
          <div className="mt-3 space-y-3">
            {message.charts.map((chart: any, i: number) => (
              <div key={i} className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                <div className="text-sm font-semibold text-gray-700 mb-2">
                  📊 {chart.title || `图表 ${i + 1}`}
                </div>
                <div className="text-xs text-gray-500 mb-1">
                  {chart.description} ({chart.chartType})
                </div>
                {chart.data && chart.data.length > 0 && (
                  <div className="text-xs text-gray-600 max-h-32 overflow-y-auto">
                    {chart.data.slice(0, 20).map((pt: any, j: number) => (
                      <span key={j} className="inline-block mr-2 mb-1 px-1.5 py-0.5 bg-white rounded border">
                        {pt.name}: {pt.value}
                      </span>
                    ))}
                    {chart.data.length > 20 && <span className="text-gray-400">+{chart.data.length - 20} more</span>}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Generated images (from MinIO) */}
        {message.images && Object.keys(message.images).length > 0 && (
          <div className="mt-2 space-y-2">
            {Object.entries(message.images).map(([filename, url]) => (
              <div key={filename}>
                <img
                  src={url}
                  alt={filename}
                  className="max-w-full rounded border border-gray-200"
                  loading="lazy"
                />
                <span className="block text-xs text-gray-400 mt-1">{filename}</span>
              </div>
            ))}
          </div>
        )}

        {/* Error indicator */}
        {message.status === 'error' && (
          <span className="block mt-1 text-xs text-red-500">
            消息发送失败
          </span>
        )}
      </div>
    </div>
  );
}
