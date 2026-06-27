# agent-chat-routing Delta Spec

## MODIFIED Requirements

### Requirement: AgentId-Based Routing
Python AI Service SHALL support an optional `agentId` parameter in chat requests. When `agentId` is present, the system SHALL load the corresponding Agent definition from Agent Repository and inject `active_agent` into LangGraph state. When `agentId` is absent, the system SHALL use the default agent configuration.

The RouterAgent-based multi-agent routing SHALL be removed. User requests SHALL flow directly into the Planning phase of the Plan → Execute → Compose workflow. Intent analysis SHALL be performed by the Planning LLM as part of execution plan generation.

#### Scenario: Request with valid agentId
- **WHEN** `POST /api/v1/generate/stream` request carries `agentId: "search-agent"`
- **THEN** system loads Search Agent definition, injects `active_agent` into graph state, and enters Planning phase

#### Scenario: Request without agentId
- **WHEN** `POST /api/v1/generate/stream` request does not carry agentId
- **THEN** system uses default agent configuration and enters Planning phase directly

#### Scenario: Request with invalid agentId
- **WHEN** `POST /api/v1/generate/stream` request carries non-existent agentId
- **THEN** system returns error event: `{ type: "message.done", status: "error", error: "Agent not found: xxx" }`

## REMOVED Requirements

### Requirement: RouterAgent Multi-Agent Selection
**Reason**: RouterAgent is replaced by Planning LLM's built-in intent analysis. The Plan → Execute → Compose workflow uses a single agent with execution plan-driven tool calls, eliminating the need for multi-agent routing.

**Migration**: All user queries now enter the Planning phase directly. The Planning LLM naturally handles intent analysis as part of plan generation. No user-facing change required.

### Requirement: CollaborationEngine Strategy Execution
**Reason**: CollaborationEngine (sequential/parallel/supervisor strategies) is replaced by plan-driven sequential execution. The execution plan provides explicit ordering, removing the need for runtime strategy selection.

**Migration**: The execution phase follows plan steps sequentially. Parallel tool execution within a single step is preserved via the existing `_parallel_tool_execution` utility.
