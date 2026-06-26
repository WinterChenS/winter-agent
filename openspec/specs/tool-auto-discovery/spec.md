# tool-auto-discovery Specification

## Purpose
TBD - created by archiving change refactor-tool-system. Update Purpose after archive.
## Requirements
### Requirement: Tool auto-discovery on startup
The system SHALL automatically discover and register tool classes from the `tools/` directory at application startup. A tool class marked with the `@tool` decorator MUST be registered without any manual code in `main.py` or other registration files.

#### Scenario: Single new tool file
- **WHEN** a developer creates `tools/my_tool/tool.py` with a class decorated with `@tool` and restarts the application
- **THEN** the tool appears in `ToolRegistry.list_tools()` output and is available for the ReAct agent to use

#### Scenario: Tool without decorator
- **WHEN** a class inherits from `BaseTool` but does NOT have the `@tool` decorator
- **THEN** the tool is NOT registered in the registry

### Requirement: Tool definitions include schema
Each discovered tool MUST expose a `schema` attribute containing a valid OpenAI function schema definition (name, description, parameters). The schema SHALL be automatically included in the LLM system prompt.

#### Scenario: Tool with complete schema
- **WHEN** a tool defines `name`, `description`, and `schema` fields
- **THEN** `ToolRegistry.list_tools()` returns all three fields for LLM prompt generation

#### Scenario: Tool with incomplete schema
- **WHEN** a tool's `schema` is missing required `parameters` field
- **THEN** the system logs a warning at startup and excludes the tool from the registry

