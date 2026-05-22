import { useState, useRef, useCallback } from 'react';
import { Message } from '../types/chat';
import { getChatHistory } from '../services/api';

interface StreamPayload {
  type?: 'token' | 'tool_start' | 'tool_result' | 'tool_summary' | 'error';
  token?: string;
  content?: string;
  conversationId?: string;
  error?: string;
  toolName?: string;
  steps?: Array<{
    tool: string;
    input: string;
    status: 'completed' | 'error';
    elapsed_ms: number;
    error?: string;
  }>;
}

interface ToolActionPayload {
  action?: string;
  tool?: string;
  query?: string;
}

function parseToolActionJson(raw: string): { toolName: string; query?: string } | null {
  const text = raw.trim();
  if (!text.startsWith('{') || !text.endsWith('}')) {
    return null;
  }

  try {
    const parsed = JSON.parse(text) as ToolActionPayload;
    const action = (parsed.action || '').trim();
    const toolName = action === 'tool' ? (parsed.tool || '').trim() : action;
    if (!toolName) {
      return null;
    }
    return { toolName, query: parsed.query };
  } catch {
    return null;
  }
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

       // 打字机队列：把后端 chunk（可能是词/短句）拆成字符后逐步渲染
       let pendingText = '';
       let isDraining = false;
       const charDelayMs = 14;

       // 控制类 JSON（如 {"action":"search"...}）缓冲，避免先展示原始 JSON 再转换
       let isCollectingControlJson = false;
       let controlJsonBuffer = '';
       let pendingToolStartName: string | null = null;
       
       // 工具步骤缓冲：用于处理 tool_summary 事件中的完整步骤列表
       let toolSummarySteps: Array<any> = [];

      const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

      const appendText = (text: string) => {
        if (!text) return;
        pendingText += text;
        void drainPendingText();
      };

      const tryConsumeAsControlJson = (chunk: string): boolean => {
        const canStartCollecting =
          !isCollectingControlJson &&
          assistantContent.trim() === '' &&
          pendingText.trim() === '' &&
          chunk.trimStart().startsWith('{');

        if (canStartCollecting) {
          isCollectingControlJson = true;
          controlJsonBuffer = '';
        }

        if (!isCollectingControlJson) {
          return false;
        }

        controlJsonBuffer += chunk;

        // 只有完整 JSON 结束时再判定，避免中间闪烁
        if (!controlJsonBuffer.includes('}')) {
          return true;
        }

        const parsed = parseToolActionJson(controlJsonBuffer);
        if (parsed) {
          pendingToolStartName = parsed.toolName;
          appendText(`\n\n🛠️ 正在调用工具：${parsed.toolName}...\n`);
          isCollectingControlJson = false;
          controlJsonBuffer = '';
          return true;
        }

        // 不是工具规划 JSON，按普通文本落回去
        appendText(controlJsonBuffer);
        isCollectingControlJson = false;
        controlJsonBuffer = '';
        return true;
      };

      const drainPendingText = async () => {
        if (isDraining) return;
        isDraining = true;

        while (pendingText.length > 0) {
          assistantContent += pendingText[0];
          pendingText = pendingText.slice(1);
          updateMessageContent(assistantMessageId, assistantContent);
          await sleep(charDelayMs);
        }

        isDraining = false;
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // 保留最后一行（可能是不完整的）在 buffer 中
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmedLine = line.trim();
          if (!trimmedLine) continue;

          if (trimmedLine.startsWith('data:')) {
            const data = trimmedLine.startsWith('data: ') ? trimmedLine.slice(6) : trimmedLine.slice(5);
            
            if (data === '[DONE]') {
              continue;
            }

            try {
              const parsed: StreamPayload = JSON.parse(data);

              // 兼容后端字段：token/content 都支持
              const textChunk = parsed.content ?? parsed.token;

              if (parsed.type === 'tool_start') {
                const incomingTool = parsed.toolName ?? 'unknown';
                // 去重：如果前面已由 action JSON 转成“正在调用工具”提示，则忽略重复 tool_start
                if (pendingToolStartName && incomingTool === pendingToolStartName) {
                  pendingToolStartName = null;
                } else {
                  appendText(parsed.content ?? `\n\n🛠️ 正在调用工具：${incomingTool}...\n`);
                }
               } else if (parsed.type === 'tool_result') {
                 pendingToolStartName = null;
                 appendText(parsed.content ?? `\n工具 ${parsed.toolName ?? 'unknown'} 执行完成。\n`);
               } else if (parsed.type === 'tool_summary') {
                 // 工具摘要事件：包含所有工具步骤的完整列表
                 if (parsed.steps && Array.isArray(parsed.steps)) {
                   toolSummarySteps = parsed.steps;
                 }
               } else if (parsed.type === 'error' || parsed.error) {
                throw new Error(parsed.error || '流式响应异常');
              } else if (textChunk) {
                // 先尝试识别并拦截规划 JSON，避免前端闪出原始 action JSON
                const consumed = tryConsumeAsControlJson(textChunk);
                if (!consumed) {
                  appendText(textChunk);
                }
              }

              if (parsed.conversationId) {
                setConversationId(parsed.conversationId);
              }
            } catch (e) {
              console.warn('解析 SSE 数据失败:', data);
            }
          }
        }
      }

      // 等待最后一段队列渲染完成，防止尾巴被截断
      while (pendingText.length > 0 || isDraining) {
        await sleep(10);
      }

      // 如果结束时还有未消费的 JSON 缓冲，作为普通文本输出
      if (controlJsonBuffer) {
        appendText(controlJsonBuffer);
        while (pendingText.length > 0 || isDraining) {
          await sleep(10);
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
