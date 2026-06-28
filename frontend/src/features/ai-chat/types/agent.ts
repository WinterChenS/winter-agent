export interface AgentInfo {
  id: string;
  name: string;
  display_name: string;
  description: string;
  enabled: boolean;
  icon?: string;
  agent_type?: string;
  system_prompt?: string;
  tools?: string[];
  model_config?: {
    model_name?: string;
    temperature?: number;
    top_p?: number;
    max_tokens?: number;
    streaming?: boolean;
    json_mode?: boolean;
  };
  trigger_keywords?: string[];
  collaboration_strategy?: string;
  priority?: number;
  tags?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface AgentCreateRequest {
  name: string;
  display_name: string;
  description?: string;
  enabled?: boolean;
  icon?: string;
  agent_type?: string;
  system_prompt?: string;
  tools?: string[];
  model_config?: AgentInfo['model_config'];
  trigger_keywords?: string[];
  collaboration_strategy?: string;
  priority?: number;
  tags?: string[];
}
