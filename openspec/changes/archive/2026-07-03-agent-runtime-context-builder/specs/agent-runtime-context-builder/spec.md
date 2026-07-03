## ADDED Requirements

### Requirement: Agent Runtime SHALL build context through a unified Context Builder
Agent Runtime SHALL collect runtime context through a single builder pipeline instead of assembling prompt context independently inside routes, nodes, or factories.

#### Scenario: build context for a conversation request
- **WHEN** a chat request includes `conversation_id`, `agent_id`, and user message text
- **THEN** the runtime SHALL create a `ContextRequest` and pass it through the Context Builder before invoking the agent or graph

#### Scenario: no provider data available
- **WHEN** no provider returns any context fragments
- **THEN** the runtime SHALL still produce a valid empty `AgentContext` and continue handling the request

### Requirement: Session history SHALL be reusable runtime context
The builder SHALL include a session provider that loads conversation history from persisted chat messages and converts it into reusable runtime context.

#### Scenario: recent messages are injected
- **WHEN** persisted messages exist for the current `conversation_id`
- **THEN** the builder SHALL load the most recent configured messages and include them in the resulting `AgentContext`

#### Scenario: internal messages are filtered
- **WHEN** history includes internal ReAct/system-only messages or non-user-visible tool noise
- **THEN** those entries SHALL be excluded from the injected session context

### Requirement: Context fragments SHALL be merged by priority and budget
The builder SHALL merge provider fragments using a stable priority order and enforce a configurable token budget.

#### Scenario: budget exceeded
- **WHEN** combined fragments exceed the configured max token budget
- **THEN** the assembler SHALL trim lower-priority or older content before producing the final rendered context

#### Scenario: session has higher priority than stubs
- **WHEN** session fragments and placeholder file/memory/knowledge fragments are both available
- **THEN** session fragments SHALL be retained ahead of lower-priority providers

### Requirement: Future providers SHALL plug into the same contract
Files, Memory, and Knowledge sources SHALL integrate through the same provider interface even if their first implementation is a stub.

#### Scenario: disabled provider
- **WHEN** a provider is configured but has no runtime source yet
- **THEN** it SHALL return an empty fragment list without breaking the builder pipeline