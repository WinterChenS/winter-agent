# agent-db-migration Specification

## Purpose
TBD - created by archiving change agent-backend-proxy. Update Purpose after archive.
## Requirements
### Requirement: Agent Definition Extended Schema
The `agent_definitions` table SHALL support extended metadata fields for visualization and categorization.

#### Scenario: New columns exist after migration
- **WHEN** migration V003 is applied
- **THEN** `agent_definitions` table includes columns: `icon VARCHAR(64)`, `agent_type VARCHAR(32)`, `avatar_url TEXT`, `is_builtin BOOLEAN DEFAULT false`, `tags JSONB DEFAULT '[]'`, `metadata JSONB DEFAULT '{}'`, `created_by VARCHAR`, `updated_by VARCHAR`, `version INTEGER DEFAULT 1`

#### Scenario: Existing data preserved after migration
- **WHEN** migration V003 is applied to a database with existing agents
- **THEN** all existing agent rows remain intact with new columns set to their DEFAULT values

### Requirement: Track agent creator and updater
The system SHALL track who created and last updated each agent definition.

#### Scenario: New agent records creator
- **WHEN** a new agent is created via API
- **THEN** `created_by` is set to the authenticated username and `version` is set to 1

#### Scenario: Updated agent records modifier
- **WHEN** an existing agent is updated via API
- **THEN** `updated_by` is set to the authenticated username and `version` is incremented

### Requirement: Agent builtin flag
The system SHALL distinguish built-in (seeded) agents from user-created agents.

#### Scenario: Seeded agents marked as builtin
- **WHEN** migration V003 runs
- **THEN** existing seed agents are backfilled with `is_builtin = true`

