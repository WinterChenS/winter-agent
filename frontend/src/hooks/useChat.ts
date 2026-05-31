import { useState, useRef, useCallback } from 'react';
import { AgentProcessStep, ChartSpecData, GuardReason, Message } from '../types/chat';
import { getChatHistory } from '../services/api';
import { parseSseChunk } from '../services/sse';

interface StreamPayload {
  type?: 'token' | 'tool_start' | 'tool_result' | 'tool_summary' | 'agent_step' | 'chart' | 'error' | 'thought' | 'reasoning_delta' | 'block' | 'block_start' | 'block_chunk' | 'block_end' | 'chart_placeholder' | 'chart_ready';
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

      const appendText = (text: string) => {
        if (!text) return;
        assistantContent += text;
        updateMessageContent(assistantMessageId, assistantContent);
      };

      const handleParsedEvent = (parsed: StreamPayload) => {
        const payload = parsed.payload ?? {};
        const textChunk = payload.content ?? parsed.content ?? parsed.token ?? '';

        // Block streaming: block_start → block_chunk → block_end
        if (parsed.type === 'block_start') {
          // Start of a new markdown block — nothing to do until chunks arrive
          return;
        }
        if (parsed.type === 'block_chunk') {
          const chunkContent = payload.content || (parsed as any).content || '';
          if (chunkContent) appendText(chunkContent);
          return;
        }
        if (parsed.type === 'block_end') {
          // Markdown block complete — append newline for spacing
          appendText('\n\n');
          return;
        }

        // Legacy monolithic block event
        if (parsed.type === 'block') {
          const block = (parsed as any).block;
          if (block?.type === 'markdown' && block?.content) {
            appendText(block.content + '\n\n');
          }
          return;
        }

        // Chart placeholder: show skeleton loading state
        if (parsed.type === 'chart_placeholder') {
          const chartId = payload.chartId || (parsed as any).chartId || 'pending';
          chartDatasForAssistant.push({ id: chartId, title: '', chartType: 'bar', description: '', data: [], _placeholder: true } as any);
          return;
        }

        // Chart ready: replace placeholder with real chart data
        if (parsed.type === 'chart_ready') {
          const spec = (payload.chartSpec || (parsed as any).chartSpec) as ChartSpecData;
          // Replace placeholder entry with real data
          chartDatasForAssistant = chartDatasForAssistant.map(c =>
            (c as any)._placeholder && c.id === spec.id ? spec : c
          );
          // Filter out any remaining placeholders
          chartDatasForAssistant = chartDatasForAssistant.filter(c => !(c as any)._placeholder);
          return;
        }

        // Legacy chart event: accumulate to attach to assistant message later
        if (parsed.type === 'chart' && (parsed as any).chartSpec) {
          chartDatasForAssistant.push((parsed as any).chartSpec as ChartSpecData);
          return;
        }

        // Thought event: show agent's reasoning step in thinking pane
        if ((parsed.type === 'thought' || parsed.type === 'reasoning_delta') && textChunk) {
          const shortThought = textChunk.length > 120 ? textChunk.slice(0, 120) + '...' : textChunk;
          const thoughtStep: ThinkingStep = {
            kind: 'reasoning',
            tool: '__reasoning__',
            title: '思考',
            summary: shortThought,
            input: shortThought,
            status: 'completed',
            elapsed_ms: 0,
            startTime: Date.now(),
          };
          if (!thinkingMessageId) {
            thinkingMessageId = addMessage({ role: 'thinking', content: '', toolSteps: [thoughtStep as any] });
          }
          thinkingSteps.push(thoughtStep);
          updateThinkingMessage();
          scrollToBottom();
          return;
        }

        // Tool started: create or update thinking pane in real-time
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
            thinkingMessageId = addMessage({
              role: 'thinking',
              content: '',
              toolSteps: [newStep as any],
            });
          }
          thinkingSteps.push(newStep);
          updateThinkingMessage();
          scrollToBottom();
          return;
        }

        // Tool completed: update the running step
        if (parsed.type === 'tool_result') {
          const toolName = payload.toolName ?? parsed.toolName ?? 'unknown';
          const contentText = textChunk || '';
          // Extract elapsed from content if available
          const now = Date.now();
          thinkingSteps = thinkingSteps.map(s => {
            if (s.tool === toolName && s.status === 'running') {
              // Try to extract input from the content
              const inputMatch = contentText.match(/query:\s*(.+?)(?:\)|$)/) ||
                                 contentText.match(/(https?:\/\/\S+)/) ||
                                 contentText.match(/读取\s*(\d+)\s*字符/);
              return {
                ...s,
                status: (payload.status === 'error' || contentText.includes('失败') || contentText.includes('ERROR')) ? 'error' as const : 'completed' as const,
                elapsed_ms: payload.elapsed_ms ?? (now - s.startTime),
                input: stringifyInput(payload.input) || (inputMatch ? inputMatch[1].trim() : s.input || ''),
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

        // Agent step: update the thinking pane and attach guard reason
        if (parsed.type === 'agent_step') {
          const incomingReason = parsed.payload?.reason ?? parsed.reason;
          if (incomingReason) {
            updateMessage(assistantMessageId, { guardReason: incomingReason as any });
            const guardStep: ThinkingStep = {
              kind: 'guard',
              tool: '__guard__',
              title: '策略收敛',
              summary: incomingReason.message || incomingReason.code || 'Agent 策略触发',
              detail: incomingReason.code,
              status: 'completed',
              elapsed_ms: 0,
              startTime: Date.now(),
            };
            if (!thinkingMessageId) {
              thinkingMessageId = addMessage({ role: 'thinking', content: '', toolSteps: [guardStep as any] });
            }
            thinkingSteps.push(guardStep);
            updateThinkingMessage();
          }
          // Auto-collapse thinking after agent step (answer is done)
          if (thinkingMessageId && thinkingSteps.length > 0) {
            updateMessage(thinkingMessageId, { content: 'done' });
          }
          return;
        }

        // Tool summary (end of stream): finalize all steps
        if (parsed.type === 'tool_summary') {
          const incomingSteps = parsed.payload?.steps ?? parsed.steps;
          if (Array.isArray(incomingSteps) && incomingSteps.length > 0) {
            // Replace steps with final, accurate data
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
          // Auto-collapse
          if (thinkingMessageId) {
            updateMessage(thinkingMessageId, { content: 'done' });
          }
          return;
        }

        if (parsed.type === 'error' || parsed.error) {
          throw new Error(parsed.error || '流式响应异常');
        }

        // Token events → assistant answer text
        const isLegacyPlainTextEvent = !parsed.type;
        const isAssistantAnswerToken = parsed.type === 'token' || isLegacyPlainTextEvent;
        if (isAssistantAnswerToken && textChunk) {
          appendText(textChunk);
        }

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
