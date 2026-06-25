# Tasks: refactor-tool-system

## Phase 1: Tool Registry Foundation

- [x] **Task 1: Add ToolSchema model and @tool decorator**
  Create `ai_service/tools/schema.py` with `ToolSchema` (OpenAI function schema) and `@tool` decorator that marks classes for auto-discovery. Tests: verify decorator sets metadata, schema validation.

- [x] **Task 2: Rewrite ToolRegistry with auto-discovery**
  Refactor `ToolRegistry` to scan `tools/` directory at startup, discover `@tool`-decorated classes, validate schemas, and auto-register. Add `build_tools_prompt()` to generate LLM tool descriptions from schemas. Tests: mock filesystem scan, verify discovery and prompt generation.

- [x] **Task 3: Migrate existing tools to @tool format**
  Update `SearchTool`, `BrowserUseTool`, `TimeTool` to use `@tool` decorator and `ToolSchema`. Remove manual registration from `main.py`. Tests: update existing tool tests.

## Phase 2: Parallel Tool Execution

- [x] **Task 4: Update agent_node for parallel tool protocol**
  Support both `{"action":"tool",...}` (legacy) and `{"actions":[...]}` (parallel) formats. Max 3 parallel tools. Tests: single tool, 2 parallel, 3 parallel, >3 limit rejection.

- [x] **Task 5: Update tool_node for parallel execution**
  Use `asyncio.gather()` when `actions` array present. Ensure error isolation (one failure doesn't block others). Tests: parallel success, mixed success/error, all error.

## Phase 3: Code Sandbox

- [x] **Task 6: Create Docker sandbox for Python execution**
  Create `ai_service/tools/sandbox/` with `docker-compose.sandbox.yml` (python:3.12-slim with pandas/numpy/matplotlib), `CodeSandboxTool` using `@tool` decorator. Network disabled, CPU 1, memory 256M, timeout 30s. Tests: successful execution, timeout, error handling.

## Phase 4: Cleanup & Integration

- [x] **Task 7: Remove manual tool registration from main.py**
  `main.py` now only needs `get_tool_registry()` — auto-discovery handles the rest. Verify startup logs show discovered tools.

- [x] **Task 8: End-to-end integration test**
  Full flow: startup auto-discovers tools → agent uses parallel search → sandbox executes Python → result flows to chart planner. Verify all 3 phases of the pipeline work with new tool system.

- [x] **Task 9: Update documentation**
  Add `ai_service/tools/README.md` explaining how to create a new tool with `@tool` decorator, schema format, and registration process.
