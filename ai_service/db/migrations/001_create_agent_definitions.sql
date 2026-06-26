CREATE TABLE IF NOT EXISTS agent_definitions (
    id VARCHAR(12) PRIMARY KEY,
    name VARCHAR(64) UNIQUE NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL,
    tools JSONB NOT NULL DEFAULT '[]',
    model_config JSONB NOT NULL DEFAULT '{"temperature": 0.7}',
    trigger_keywords JSONB NOT NULL DEFAULT '[]',
    collaboration_strategy VARCHAR(16) NOT NULL DEFAULT 'sequential',
    priority INT NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
