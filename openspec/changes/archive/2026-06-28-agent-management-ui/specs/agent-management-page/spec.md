## ADDED Requirements

### Requirement: Agent Management Page
The system SHALL provide an Agent Management page at `/agents` with Card-based layout, search, pagination, and sorting capabilities.

#### Scenario: Card layout displays agents
- **WHEN** user navigates to `/agents`
- **THEN** agents are displayed as Cards (not table rows), each showing icon, name, agent_type, tags, and enabled status

#### Scenario: Empty state
- **WHEN** no agents exist
- **THEN** page shows an empty state illustration with "Create your first agent" prompt

#### Scenario: Loading state
- **WHEN** agents are being fetched
- **THEN** skeleton cards are displayed as placeholders

#### Scenario: Search agents
- **WHEN** user types in the search input
- **THEN** the agent list is filtered by name or display_name

#### Scenario: Pagination
- **WHEN** there are more than the page size agents
- **THEN** pagination controls appear allowing navigation between pages

#### Scenario: Hover effect
- **WHEN** user hovers over an agent card
- **THEN** the card elevates with shadow and shows action buttons (Edit, Clone, Enable/Disable, Delete)

### Requirement: Agent Enable/Disable Toggle
The system SHALL support enabling and disabling agents directly from the management page.

#### Scenario: Disable an agent
- **WHEN** user clicks disable on an enabled agent
- **THEN** the agent's enabled status toggles to false and the card updates

#### Scenario: Enable an agent
- **WHEN** user clicks enable on a disabled agent
- **THEN** the agent's enabled status toggles to true and the card updates

### Requirement: Agent Drawer Editor
The system SHALL open a Drawer (not Modal) when editing or creating an agent, with grouped sections: Basic Info, Prompt, Model, Tools, Trigger, Advanced.

#### Scenario: Create new agent
- **WHEN** user clicks "+ New Agent" button
- **THEN** a Drawer opens from the right with an empty form

#### Scenario: Edit existing agent
- **WHEN** user clicks "Edit" on an agent card
- **THEN** a Drawer opens with the agent's data pre-filled

#### Scenario: Drawer sections
- **WHEN** the Drawer is open
- **THEN** it shows collapsible sections: Basic Info (name/icon/description), Prompt (CodeMirror editor), Model (model_name/temperature/top_p/max_tokens/streaming), Tools (multi-select checkboxes), Trigger (tag input), Advanced (collaboration_strategy/priority)

#### Scenario: Delete agent
- **WHEN** user clicks "Delete" on an agent card
- **THEN** a confirmation dialog appears, and upon confirmation the agent is deleted

#### Scenario: Clone agent
- **WHEN** user clicks "Clone" on an agent card
- **THEN** the agent is cloned via the API and a new card appears in the list
