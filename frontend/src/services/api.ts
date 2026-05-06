export async function streamChat(
  message: string,
  onToken: (token: string) => void,
  conversationId?: string
): Promise<string | undefined> {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
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
  let finalConversationId: string | undefined;
  let buffer = '';

  try {
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
            const parsed = JSON.parse(data);
            if (parsed.content) {
              onToken(parsed.content);
            }
            if (parsed.conversationId) {
              finalConversationId = parsed.conversationId;
            }
            if (parsed.error) {
              throw new Error(parsed.error);
            }
          } catch (e) {
            console.warn('解析 SSE 数据失败:', data);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  return finalConversationId;
}

export async function getChatHistory(conversationId: string): Promise<any[]> {
  const response = await fetch(`/api/chat/history/${conversationId}`);
  if (!response.ok) {
    throw new Error('获取历史记录失败');
  }
  const data = await response.json();
  return data.messages || [];
}
