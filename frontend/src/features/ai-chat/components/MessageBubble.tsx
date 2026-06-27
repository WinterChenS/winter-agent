import type { Message } from '../types/message';
import { ReasoningPanel } from './ReasoningPanel';
import { ToolCallPanel } from './ToolCallPanel';
import { MarkdownRenderer } from './MarkdownRenderer';
import { StreamingRenderer } from './StreamingRenderer';
import ReactECharts from 'echarts-for-react';

interface MessageBubbleProps {
  message: Message;
}

function chartSpecToOption(chart: any) {
  const { title, chartType, description, xAxisLabel, yAxisLabel, data = [] } = chart;
  const names = data.map((d: any) => d.name);
  const values = data.map((d: any) => d.value);
  const groups = [...new Set(data.map((d: any) => d.group).filter(Boolean))];

  const baseOption: any = {
    title: { text: title, subtext: description, left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    legend: groups.length > 0 ? { data: groups, bottom: 0 } : undefined,
    grid: { left: '3%', right: '4%', bottom: groups.length > 0 ? '12%' : '8%', containLabel: true },
    xAxis: { type: 'category', data: names, name: xAxisLabel },
    yAxis: { type: 'value', name: yAxisLabel },
    series: [],
  };

  if (chartType === 'pie') {
    return {
      title: baseOption.title,
      tooltip: { trigger: 'item' },
      legend: { bottom: 0 },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: data.map((d: any) => ({ name: d.name, value: d.value })),
        label: { formatter: '{b}: {c}' },
      }],
    };
  }

  if (groups.length > 0) {
    baseOption.series = groups.map((g: string) => ({
      type: chartType === 'bar' ? 'bar' : 'line',
      name: g,
      data: data.filter((d: any) => d.group === g).map((d: any) => d.value),
    }));
  } else {
    baseOption.series = [{
      type: chartType === 'bar' ? 'bar' : 'line',
      data: values,
      itemStyle: chartType === 'bar' ? undefined : { color: '#5470c6' },
    }];
  }

  return baseOption;
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
          <div className="mt-3 space-y-4">
            {message.charts.map((chart: any, i: number) => (
              <div key={i} className="bg-white border border-gray-200 rounded-lg p-2">
                <ReactECharts
                  option={chartSpecToOption(chart)}
                  style={{ height: 300, width: '100%' }}
                  opts={{ renderer: 'canvas' }}
                />
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
