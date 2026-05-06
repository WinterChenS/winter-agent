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

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n').filter(line => line.trim());

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          
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
