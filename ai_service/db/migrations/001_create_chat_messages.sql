-- 001_create_chat_messages.sql
-- New table for unified message persistence (AI Chat Layer Rewrite)

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL DEFAULT '',
    reasoning TEXT,
    tool_calls JSONB,
    status VARCHAR(16) DEFAULT 'done' CHECK (status IN ('streaming', 'done', 'error')),
    agent_id VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conv
    ON chat_messages(conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_messages_agent
    ON chat_messages(agent_id, created_at);
