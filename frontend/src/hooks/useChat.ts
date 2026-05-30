import { useState, useRef, useCallback } from 'react';
import { ChartSpecData, GuardReason, Message } from '../types/chat';
import { getChatHistory } from '../services/api';
import { parseSseChunk } from '../services/sse';

interface StreamPayload {
  type?: 'token' | 'tool_start' | 'tool_result' | 'tool_summary' | 'agent_step' | 'chart' | 'error';
  schemaVersion?: string;
  payload?: {
    reason?: GuardReason;
    steps?: Array<{
      tool: string;
      input: string;
      status: 'completed' | 'error';
      elapsed_ms: number;
      error?: string;
    }>;
  };
  token?: string;
  content?: string;
  conversationId?: string;
  error?: string;
  toolName?: string;
  reason?: GuardReason;
  steps?: Array<{
    tool: string;
    input: string;
    status: 'completed' | 'error';
    elapsed_ms: number;
    error?: string;
  }>;
}

interface ThinkingStep {
  tool: string;
  input: string;
  status: 'running' | 'completed' | 'error';
  elapsed_ms?: number;
  error?: string;
  startTime: number;
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
      const chartData = (history as any).chartData;
      const toolSteps = (history as any).toolSteps;

      const formatted: Message[] = history.messages.map((msg: any) => ({
        id: crypto.randomUUID(),
        role: msg.role as Message['role'],
        content: msg.content,
        timestamp: Date.now(),
      }));

      // Attach chart data to the last assistant message
      if (chartData && formatted.length > 0) {
        for (let i = formatted.length - 1; i >= 0; i--) {
          if (formatted[i].role === 'assistant') {
            formatted[i] = { ...formatted[i], chartData };
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
          toolSteps: toolSteps.map((s: any) => ({ ...s, status: 'completed' as const })),
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
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      let chartDataForAssistant: ChartSpecData | undefined;

      const appendText = (text: string) => {
        if (!text) return;
        assistantContent += text;
        updateMessageContent(assistantMessageId, assistantContent);
      };

      const handleParsedEvent = (parsed: StreamPayload) => {
        const textChunk = parsed.content ?? parsed.token ?? '';

        // Chart event: store to attach to assistant message later
        if (parsed.type === 'chart' && (parsed as any).chartSpec) {
          chartDataForAssistant = (parsed as any).chartSpec as ChartSpecData;
          return;
        }

        // Tool started: create or update thinking pane in real-time
        if (parsed.type === 'tool_start') {
          const toolName = parsed.toolName ?? 'unknown';
          const newStep: ThinkingStep = {
            tool: toolName,
            input: '',
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
          const toolName = parsed.toolName ?? 'unknown';
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
                status: contentText.includes('失败') || contentText.includes('ERROR') ? 'error' as const : 'completed' as const,
                elapsed_ms: now - s.startTime,
                input: inputMatch ? inputMatch[1].trim() : s.input || contentText.slice(0, 80),
                error: contentText.includes('失败') ? contentText.slice(0, 100) : undefined,
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
              tool: s.tool || 'unknown',
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
      if (chartDataForAssistant) {
        updateMessage(assistantMessageId, { chartData: chartDataForAssistant as any });
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
