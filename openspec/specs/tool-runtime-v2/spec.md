# tool-runtime-v2 Specification

## Purpose
TBD - created by archiving change agent-runtime-tool-v2. Update Purpose after archive.
## Requirements
### Requirement: Agent Runtime SHALL use native LLM tool_calls for tool invocation
The `agent_node` SHALL bind registered tools to the LLM using `bind_tools` and route execution based on the presence of `tool_calls` in the LLM response, instead of parsing JSON text.

#### Scenario: LLM returns tool_calls
- **WHEN** the LLM response contains one or more `tool_calls`
- **THEN** the agent_node SHALL route to the tool_node with the structured tool call data

#### Scenario: LLM returns no tool_calls
- **WHEN** the LLM response contains no `tool_calls` and the agent has collected evidence
- **THEN** the agent_node SHALL route to chart_planner for final answer generation

#### Scenario: bind_tools not supported by provider
- **WHEN** the configured LLM provider does not support native tool calling
- **THEN** the runtime SHALL fall back to the existing JSON Mode path or raise a clear configuration error

### Requirement: Tool schemas SHALL support semantic versioning
Each tool definition SHALL support versioned schemas with backward compatibility checking.

#### Scenario: multiple schema versions coexist
- **WHEN** a tool has both v1.0.0 and v2.0.0 schemas registered
- **THEN** the runtime SHALL serve the latest version by default and allow callers to request a specific version

#### Scenario: deprecated parameter in new version
- **WHEN** a schema version marks a parameter as deprecated
- **THEN** the runtime SHALL accept calls using the deprecated parameter and include a deprecation warning

### Requirement: Tool execution results SHALL stream real-time progress via SSE
The tool_node SHALL emit streaming progress events through the StreamingEventBus for long-running tool executions.

#### Scenario: tool execution with progress
- **WHEN** a tool supports streaming progress updates
- **THEN** the SSE stream SHALL emit `tool.progress` and `tool.output` events before the final `tool.completed` event

#### Scenario: tool completes without streaming support
- **WHEN** a tool does not support streaming (legacy or fast-executing)
- **THEN** the SSE stream SHALL emit only `tool.completed` with the execution result

#### Scenario: legacy tool without execute_stream
- **WHEN** a tool only implements `execute()` without overriding `execute_stream()`
- **THEN** the tool_node SHALL automatically emit `tool.started` before execution and `tool.completed` after execution, maintaining backward compatibility

### Requirement: ToolRegistry SHALL support lifecycle hooks and metrics
The ToolRegistry SHALL provide pre/post-execution hooks and collect per-tool invocation metrics.

#### Scenario: pre-execution hook
- **WHEN** a pre-execution hook is registered for a tool
- **THEN** the hook SHALL execute before the tool's `execute` method, and SHALL be able to modify or reject the input

#### Scenario: metrics collection
- **WHEN** a tool is invoked
- **THEN** the registry SHALL record invocation count, execution latency, and error status for later querying

### Requirement: Tool schemas SHALL adapt to multiple LLM providers
The ToolSchemaAdapter SHALL convert tool definitions between OpenAI and Anthropic formats.

#### Scenario: OpenAI format tool schema
- **WHEN** the active LLM provider is OpenAI-compatible
- **THEN** the adapter SHALL output `{"type": "function", "function": {"name": "...", "parameters": {...}}}` format

#### Scenario: Anthropic format tool schema
- **WHEN** the active LLM provider is Anthropic
- **THEN** the adapter SHALL output Anthropic-native tool use format with `name`, `description`, `input_schema`

