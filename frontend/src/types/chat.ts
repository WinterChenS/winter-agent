export interface GuardReason {
  node?: string;
  code?: string;
  message?: string;
  timestamp?: number;
  extra?: Record<string, unknown>;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool_summary' | 'agent_step';
  content: string;
  timestamp: number;
  toolSteps?: Array<{
    tool: string;
    input: string;
    status: 'completed' | 'error';
    elapsed_ms: number;
    error?: string;
  }>;
  guardReason?: GuardReason;
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
