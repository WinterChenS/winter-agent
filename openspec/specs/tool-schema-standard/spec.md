# tool-schema-standard Specification

## Purpose
TBD - created by archiving change refactor-tool-system. Update Purpose after archive.
## Requirements
### Requirement: Tool schema follows OpenAI function format
All tools MUST define their input schema using the OpenAI function calling `parameters` format (JSON Schema subset). The system SHALL use this schema to generate the agent's tool description prompt automatically.

#### Scenario: Standard schema generates correct prompt
- **WHEN** a tool defines `schema.parameters` with `type`, `required`, and `properties`
- **THEN** `ToolRegistry.build_tools_prompt()` generates a complete tool description including parameter types and descriptions

#### Scenario: Agent uses schema in tool call
- **WHEN** the agent calls a tool with JSON like `{"action":"tool","tool":"search","query":"..."}`
- **THEN** the query parameter matches a property defined in the tool's schema

### Requirement: Tool result standardization
All tool execution results MUST use a unified format: `{"ok": bool, "data": dict, "error": {"code": str, "message": str}}`. The system SHALL normalize results before passing them to the LLM as observations.

#### Scenario: Successful tool execution
- **WHEN** a tool executes successfully
- **THEN** the result contains `"ok": true` and `"data"` with tool-specific content

#### Scenario: Failed tool execution
- **WHEN** a tool execution fails
- **THEN** the result contains `"ok": false` and `"error"` with `code` and `message`

