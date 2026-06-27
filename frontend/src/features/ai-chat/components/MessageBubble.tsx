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
          <div className="whitespace-pre-wrap">{message.content}</div>
        ) : (
          <StreamingRenderer isStreaming={isStreaming}>
            <MarkdownRenderer content={message.content} />
          </StreamingRenderer>
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
