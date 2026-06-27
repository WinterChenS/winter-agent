// frontend/src/types/chat.ts
// @deprecated — Old message types kept for AdminAgents compatibility.
// New AI Chat UI uses features/ai-chat/types/message.ts

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: "pending" | "running" | "done" | "failed";
  result?: unknown;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  reasoning?: string;
  toolCalls?: ToolCall[];
  status: "streaming" | "done" | "error";
  agentId?: string;
  conversationId?: string;
  createdAt?: number;
}

// Keep old types for backward compat with Sidebar/system components
export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
}

export interface AgentDefinition {
  id: string;
  name: string;
  display_name: string;
  description: string;
  enabled: boolean;
}
