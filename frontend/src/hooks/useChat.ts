import { useState, useRef, useCallback } from 'react';
import { GuardReason, Message } from '../types/chat';
import { getChatHistory } from '../services/api';
import { parseSseChunk } from '../services/sse';

interface StreamPayload {
  type?: 'token' | 'tool_start' | 'tool_result' | 'tool_summary' | 'agent_step' | 'error';
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
      const formatted = history.map((msg: any) => ({
        id: crypto.randomUUID(),
        role: msg.role,
        content: msg.content,
        timestamp: Date.now(),
      }));
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

  const updateMessageContent = useCallback((id: string, content: string) => {
    setMessages(prev => prev.map(msg => 
      msg.id === id ? { ...msg, content } : msg
    ));
    setTimeout(scrollToBottom, 10);
  }, [scrollToBottom]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isSending) return;

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
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: content.trim(),
          conversationId,
        }),
      });

      if (!response.ok) {
        throw new Error('请求失败');
      }

      if (!response.body) {
        throw new Error('响应体为空');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';
      let buffer = '';
      let toolSummarySteps: NonNullable<Message['toolSteps']> = [];
      let guardReason: GuardReason | undefined;

      const appendText = (text: string) => {
        if (!text) return;
        assistantContent += text;
        updateMessageContent(assistantMessageId, assistantContent);
      };

      const handleParsedEvent = (parsed: StreamPayload) => {
        const incomingSteps = parsed.payload?.steps ?? parsed.steps;
        const incomingReason = parsed.payload?.reason ?? parsed.reason;
        const textChunk = parsed.content ?? parsed.token ?? '';

        if (parsed.type === 'tool_summary' && Array.isArray(incomingSteps)) {
          toolSummarySteps = incomingSteps;
          return;
        }

        if (parsed.type === 'agent_step' && incomingReason) {
          guardReason = incomingReason;
          return;
        }

        if (parsed.type === 'error' || parsed.error) {
          throw new Error(parsed.error || '流式响应异常');
        }

        // Inline tool events: show tool start/result in the assistant bubble
        if (parsed.type === 'tool_start' || parsed.type === 'tool_result') {
          if (parsed.type === 'tool_start') {
            appendText(`\n\n🛠️ 正在调用工具：${parsed.toolName ?? 'unknown'}...\n`);
          } else {
            appendText(textChunk || `\n工具 ${parsed.toolName ?? 'unknown'} 执行完成。\n`);
          }
          return;
        }

        // Token events and legacy plain-text events → assistant answer text
        const isLegacyPlainTextEvent = !parsed.type;
        const isAssistantAnswerToken = parsed.type === 'token' || isLegacyPlainTextEvent;
        if (isAssistantAnswerToken && textChunk) {
          appendText(textChunk);
        }

        if (parsed.conversationId) {
          setConversationId(parsed.conversationId);
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const { events, rest } = parseSseChunk(buffer);
        buffer = rest;

        for (const rawEvent of events) {
          if (rawEvent === '[DONE]') {
            continue;
          }

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

      // Flush trailing frame when stream ends without final separator.
      if (buffer.trim()) {
        const { events } = parseSseChunk(`${buffer}\n\n`);
        for (const rawEvent of events) {
          if (rawEvent === '[DONE]') continue;

          let parsed: StreamPayload;
          try {
            parsed = JSON.parse(rawEvent) as StreamPayload;
          } catch {
            console.warn('解析 SSE 尾帧失败:', rawEvent);
            continue;
          }

          handleParsedEvent(parsed);
        }
      }

      // 如果收到了 tool_summary 事件且有工具步骤，创建独立的工具摘要消息
      if (toolSummarySteps && toolSummarySteps.length > 0) {
        addMessage({
          role: 'tool_summary',
          content: '工具执行步骤',
          toolSteps: toolSummarySteps,
        });
      }

      if (guardReason) {
        const codeText = guardReason.code ? `（${guardReason.code}）` : '';
        addMessage({
          role: 'agent_step',
          content: guardReason.message || `Agent 执行策略已触发${codeText}`,
          guardReason,
        });
      }
    } catch (err) {
      updateMessageContent(assistantMessageId, '抱歉，AI 服务暂时不可用，请稍后再试。');
      console.error('发送消息失败:', err);
    } finally {
      setIsSending(false);
    }
  }, [isSending, conversationId, addMessage, updateMessageContent]);

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
