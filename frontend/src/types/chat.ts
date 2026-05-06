export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface ChatRequest {
  message: string;
  conversationId?: string;
}

export interface ChatResponse {
  content: string;
  conversationId?: string;
}

export interface StreamEvent {
  type: 'token' | 'done' | 'error';
  data: string;
}
