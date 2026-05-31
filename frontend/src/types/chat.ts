export interface GuardReason {
  node?: string;
  code?: string;
  message?: string;
  timestamp?: number;
  extra?: Record<string, unknown>;
}

export interface ChartDataPoint {
  name: string;
  value: number;
  group?: string;
}

export interface ChartSpecData {
  id: string;
  title: string;
  chartType: 'line' | 'bar' | 'pie' | 'scatter' | 'area' | 'radar';
  description: string;
  xAxisLabel?: string;
  yAxisLabel?: string;
  data: ChartDataPoint[];
}

export interface AgentProcessStep {
  id?: string;
  kind?: 'reasoning' | 'tool' | 'guard';
  tool?: string;
  title?: string;
  summary?: string;
  input?: string;
  detail?: string;
  status: 'completed' | 'error' | 'running';
  elapsed_ms?: number;
  error?: string;
  startTime?: number;
}

export interface ContentBlock {
  type: 'text' | 'chart';
  content?: string;
  chartId?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool_summary' | 'agent_step' | 'chart' | 'thinking';
  content: string;
  timestamp: number;
  toolSteps?: AgentProcessStep[];
  guardReason?: GuardReason;
  chartDatas?: ChartSpecData[];
  contentBlocks?: ContentBlock[];
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
