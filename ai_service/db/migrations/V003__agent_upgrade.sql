-- ================================================================
-- Migration V003: Agent table upgrade — new fields extension
-- Run: psql $DATABASE_URL -f ai_service/db/migrations/V003__agent_upgrade.sql
-- ================================================================

BEGIN;

ALTER TABLE agent_definitions
    ADD COLUMN IF NOT EXISTS icon VARCHAR(64) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS agent_type VARCHAR(32) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS avatar_url TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS is_builtin BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS created_by VARCHAR NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS updated_by VARCHAR NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- Backfill: mark known seed agents as built-in
UPDATE agent_definitions SET is_builtin = true
WHERE name IN ('search', 'code_analyst', 'web_researcher', 'general', 'data_analyst');

COMMIT;
