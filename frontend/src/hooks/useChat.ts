import { useState, useRef, useCallback } from 'react';
import { AgentProcessStep, ChartSpecData, GuardReason, Message } from '../types/chat';
import { getChatHistory } from '../services/api';
import { parseSseChunk } from '../services/sse';

interface StreamPayload {
  type?: 'token' | 'tool_start' | 'tool_result' | 'tool_summary' | 'agent_step' | 'chart' | 'error' | 'thought' | 'reasoning_delta';
  schemaVersion?: string;
  payload?: {
    content?: string;
    toolName?: string;
    input?: unknown;
    status?: 'running' | 'completed' | 'error';
    summary?: string;
    elapsed_ms?: number;
    error?: string;
    chartId?: string;
    chartSpec?: ChartSpecData;
    block?: unknown;
    reason?: GuardReason;
    steps?: AgentProcessStep[];
  };
  token?: string;
  content?: string;
  conversationId?: string;
  error?: string;
  toolName?: string;
  reason?: GuardReason;
  steps?: AgentProcessStep[];
}

type ThinkingStep = AgentProcessStep & { startTime: number };

function stringifyInput(input: unknown): string {
  if (input == null) return '';
  if (typeof input === 'string') return input;
  if (typeof input === 'object') {
    const maybeQuery = (input as any).query ?? (input as any).url;
    if (maybeQuery) return String(maybeQuery);
    try {
      return JSON.stringify(input);
    } catch {
      return String(input);
    }
  }
  return String(input);
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [conversationId, setConversationId] = useState<string>();

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const loadHistory = useCallback(async (existingId: string) => {
    try {
      const history = await getChatHistory(existingId);
      const chartDatas: ChartSpecData[] = (history as any).chartDatas ||
        ((history as any).chartData ? [(history as any).chartData] : []);
      const toolSteps = (history as any).toolSteps;

      const formatted: Message[] = history.messages.map((msg: any) => ({
        id: crypto.randomUUID(),
        role: msg.role as Message['role'],
        content: msg.content,
        timestamp: Date.now(),
      }));

      // Attach chart data to the last assistant message
      if (chartDatas.length > 0 && formatted.length > 0) {
        for (let i = formatted.length - 1; i >= 0; i--) {
          if (formatted[i].role === 'assistant') {
            formatted[i] = { ...formatted[i], chartDatas };
            break;
          }
        }
      }

      // Insert thinking pane before the last assistant message
      if (toolSteps && toolSteps.length > 0 && formatted.length > 0) {
        // Find the last assistant message index
        let insertIdx = formatted.length;
        for (let i = formatted.length - 1; i >= 0; i--) {
          if (formatted[i].role === 'assistant') {
            insertIdx = i;
          }
        }
        const thinkingMsg: Message = {
          id: crypto.randomUUID(),
          role: 'thinking',
          content: 'done',
          toolSteps: toolSteps.map((s: any) => ({
            kind: s.kind || 'tool',
            tool: s.tool || 'unknown',
            title: s.title || `调用 ${s.tool || 'tool'}`,
            summary: s.summary || '',
            input: s.input || '',
            status: s.status === 'error' ? 'error' as const : 'completed' as const,
            elapsed_ms: s.elapsed_ms || 0,
            error: s.error,
          })),
          timestamp: Date.now() - 1,
        };
        formatted.splice(insertIdx, 0, thinkingMsg);
      }

      setMessages(formatted);
      setConversationId(existingId);
      setTimeout(scrollToBottom, 100);
    } catch (e) {
      console.error('加载历史记录失败', e);
    }
  }, [scrollToBottom]);

  const addMessage = useCallback((message: Omit<Message, 'id' | 'timestamp'>) => {
    const newMessage: Message = {
      ...message,
      id: crypto.randomUUID(),
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, newMessage]);
    setTimeout(scrollToBottom, 50);
    return newMessage.id;
  }, [scrollToBottom]);

  const updateMessage = useCallback((id: string, updates: Partial<Message>) => {
    setMessages(prev => prev.map(msg =>
      msg.id === id ? { ...msg, ...updates } : msg
    ));
    setTimeout(scrollToBottom, 10);
  }, [scrollToBottom]);

  const updateMessageContent = useCallback((id: string, content: string) => {
    updateMessage(id, { content });
  }, [updateMessage]);

  const sendMessage = useCallback(async (content: string, overrideConversationId?: string) => {
    if (!content.trim() || isSending) return;

    const effectiveConversationId = overrideConversationId ?? conversationId;

    addMessage({
      role: 'user',
      content: content.trim(),
    });

    const assistantMessageId = addMessage({
      role: 'assistant',
      content: '',
    });

    setIsSending(true);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: content.trim(),
          conversationId: effectiveConversationId,
        }),
      });

      if (!response.ok) throw new Error('请求失败');
      if (!response.body) throw new Error('响应体为空');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';
      let buffer = '';
      let thinkingSteps: ThinkingStep[] = [];
      let thinkingMessageId: string | null = null;
      let chartDatasForAssistant: ChartSpecData[] = [];
      let chartDataCache: Map<string, ChartSpecData> = new Map();
      let textBuffer = "";

      const appendText = (text: string) => {
        if (!text) return;
        assistantContent += text;
        updateMessageContent(assistantMessageId, assistantContent);
      };

      const handleParsedEvent = (parsed: StreamPayload) => {
        const payload = parsed.payload ?? {};
        const textChunk = payload.content ?? parsed.content ?? parsed.token ?? '';

        // Chart data received (from Phase 2 chart_planner_node via SSE)
        if (parsed.type === 'chart' && (parsed as any).chartSpec) {
          const spec = (parsed as any).chartSpec as ChartSpecData;
          const key = String(spec.id ?? '0');
          chartDataCache.set(key, spec);
          return;
        }

        // Legacy chart event (chartSpec in payload without type)
        if ((parsed as any).chartSpec && !parsed.type) {
          const spec = (parsed as any).chartSpec as ChartSpecData;
          chartDataCache.set(String(spec.id ?? '0'), spec);
          return;
        }

        // Token event: buffer across events to find [CHART:n] markers
        if ((parsed.type === 'token' || !parsed.type) && textChunk) {
          textBuffer += textChunk;

          // Process complete markers in buffer
          const markerRe = /\[CHART:\d+\]/g;
          let match;
          let lastIndex = 0;
          let hasMarker = false;

          while ((match = markerRe.exec(textBuffer)) !== null) {
            hasMarker = true;
            // Flush text before marker
            if (match.index > lastIndex) {
              appendText(textBuffer.slice(lastIndex, match.index));
            }
            // Process marker
            const chartId = match[0].match(/\d+/)?.[0];
            if (chartId) {
              const spec = chartDataCache.get(chartId);
              if (spec) {
                chartDatasForAssistant = [...chartDatasForAssistant, spec];
              }
            }
            lastIndex = markerRe.lastIndex;
          }

          if (hasMarker) {
            // Keep only unprocessed text after last marker
            textBuffer = textBuffer.slice(lastIndex);
          } else if (textBuffer.length > 20) {
            // No marker found, buffer is large enough — flush as text
            // But keep last 20 chars in case they're a partial [CHART:n]
            const safeLen = textBuffer.length - 20;
            appendText(textBuffer.slice(0, safeLen));
            textBuffer = textBuffer.slice(safeLen);
          }
          return;
        }

        // Tool started
        if (parsed.type === 'tool_start') {
          const toolName = payload.toolName ?? parsed.toolName ?? 'unknown';
          const input = stringifyInput(payload.input);
          const newStep: ThinkingStep = {
            kind: 'tool',
            tool: toolName,
            title: `调用 ${toolName}`,
            summary: input ? `输入：${input}` : '准备执行工具',
            input,
            status: 'running',
            startTime: Date.now(),
          };
          if (!thinkingMessageId) {
            thinkingMessageId = addMessage({ role: 'thinking', content: '', toolSteps: [newStep as any] });
          }
          thinkingSteps.push(newStep);
          updateThinkingMessage();
          scrollToBottom();
          return;
        }

        // Tool completed
        if (parsed.type === 'tool_result') {
          const toolName = payload.toolName ?? parsed.toolName ?? 'unknown';
          const contentText = textChunk || '';
          const now = Date.now();
          thinkingSteps = thinkingSteps.map(s => {
            if (s.tool === toolName && s.status === 'running') {
              return {
                ...s,
                status: (payload.status === 'error' || contentText.includes('失败') || contentText.includes('ERROR')) ? 'error' as const : 'completed' as const,
                elapsed_ms: payload.elapsed_ms ?? (now - s.startTime),
                input: stringifyInput(payload.input) || s.input || '',
                summary: payload.summary || contentText.trim() || s.summary,
                detail: contentText.trim(),
                error: payload.error || (contentText.includes('失败') ? contentText.slice(0, 100) : undefined),
              };
            }
            return s;
          });
          updateThinkingMessage();
          return;
        }

        // Final tool summary
        if (parsed.type === 'tool_summary') {
          const incomingSteps = parsed.payload?.steps ?? parsed.steps;
          if (Array.isArray(incomingSteps) && incomingSteps.length > 0) {
            thinkingSteps = incomingSteps.map((s: any) => ({
              kind: s.kind || 'tool',
              tool: s.tool || 'unknown',
              title: s.title || `调用 ${s.tool || 'tool'}`,
              summary: s.summary || '',
              input: s.input || '',
              status: (s.status === 'error' ? 'error' : 'completed') as ThinkingStep['status'],
              elapsed_ms: s.elapsed_ms || 0,
              error: s.error,
              startTime: Date.now() - (s.elapsed_ms || 0),
            }));
            updateThinkingMessage();
          }
          if (thinkingMessageId) {
            updateMessage(thinkingMessageId, { content: 'done' });
          }
          return;
        }

        // Agent step / guard reason
        if (parsed.type === 'agent_step') {
          const incomingReason = parsed.payload?.reason ?? parsed.reason;
          if (incomingReason) {
            updateMessage(assistantMessageId, { guardReason: incomingReason as any });
          }
          if (thinkingMessageId && thinkingSteps.length > 0) {
            updateMessage(thinkingMessageId, { content: 'done' });
          }
          return;
        }

        // Thought / reasoning delta — ignore in new protocol
        if (parsed.type === 'thought' || parsed.type === 'reasoning_delta') {
          return;
        }

        // Error
        if (parsed.type === 'error' || parsed.error) {
          throw new Error(parsed.error || 'Stream response error');
        }

        // Conversation ID capture
        if (parsed.conversationId) {
          setConversationId(parsed.conversationId);
        }
      };

      const updateThinkingMessage = () => {
        if (thinkingMessageId) {
          const allDone = thinkingSteps.every(s => s.status !== 'running');
          updateMessage(thinkingMessageId, {
            toolSteps: thinkingSteps as any,
            content: allDone ? 'done' : 'running',
          });
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const { events, rest } = parseSseChunk(buffer);
        buffer = rest;

        for (const rawEvent of events) {
          if (rawEvent === '[DONE]') continue;
          let parsed: StreamPayload;
          try {
            parsed = JSON.parse(rawEvent) as StreamPayload;
          } catch {
            console.warn('解析 SSE 数据失败:', rawEvent);
            continue;
          }
          handleParsedEvent(parsed);
        }
      }

      // Flush trailing frame
      if (buffer.trim()) {
        const { events } = parseSseChunk(`${buffer}\n\n`);
        for (const rawEvent of events) {
          if (rawEvent === '[DONE]') continue;
          let parsed: StreamPayload;
          try { parsed = JSON.parse(rawEvent) as StreamPayload; } catch { continue; }
          handleParsedEvent(parsed);
        }
      }

      // Flush remaining text buffer at end of stream
      if (textBuffer) {
        appendText(textBuffer);
        textBuffer = '';
      }

      // Attach chart data to the assistant message
      if (chartDatasForAssistant.length > 0) {
        updateMessage(assistantMessageId, { chartDatas: chartDatasForAssistant as any });
      }
    } catch (err) {
      updateMessageContent(assistantMessageId, '抱歉，AI 服务暂时不可用，请稍后再试。');
      console.error('发送消息失败:', err);
    } finally {
      setIsSending(false);
    }
  }, [isSending, conversationId, addMessage, updateMessage, updateMessageContent]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setConversationId(undefined);
  }, []);

  return {
    messages,
    isSending,
    messagesEndRef,
    sendMessage,
    clearMessages,
    loadHistory,
    setConversationId,
  };
}
