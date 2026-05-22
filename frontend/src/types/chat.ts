export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool_summary';
  content: string;
  timestamp: number;
  toolSteps?: Array<{
    tool: string;
    input: string;
    status: 'completed' | 'error';
    elapsed_ms: number;
    error?: string;
  }>;
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

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
}
