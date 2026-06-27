# parallel-tool-execution Specification

## Purpose
TBD - created by archiving change refactor-tool-system. Update Purpose after archive.
## Requirements
### Requirement: Agent can call multiple tools in parallel
The agent SHALL be able to request multiple independent tool calls in a single ReAct iteration using the `actions` array format. The system MUST execute all tools concurrently and return all results in a single observation.

#### Scenario: Two independent search queries
- **WHEN** the agent outputs `{"actions":[{"tool":"search","query":"GDP排名"},{"tool":"search","query":"出生率数据"}]}`
- **THEN** both searches execute concurrently and results are returned together as observation

#### Scenario: Maximum parallel limit enforced
- **WHEN** the agent requests more than 3 tools in a single `actions` array
- **THEN** only the first 3 are executed and a warning is logged

### Requirement: Parallel execution preserves error isolation
A failure in one parallel tool call SHALL NOT prevent other parallel calls from completing. The observation MUST include both success and failure results.

#### Scenario: One tool fails in parallel batch
- **WHEN** 2 tools are called in parallel and one returns an error
- **THEN** the observation contains the successful result for tool 1 and the error for tool 2

### Requirement: Backward compatible with single tool calls
The existing single-tool format `{"action":"tool","tool":"...","query":"..."}` SHALL continue to work without modification.

#### Scenario: Existing single tool call still works
- **WHEN** the agent outputs the legacy format `{"action":"tool","tool":"search","query":"test"}`
- **THEN** the tool executes normally as before

