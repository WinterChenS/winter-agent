# Comet Design Handoff

- Change: refactor-tool-system
- Phase: design
- Mode: compact
- Context hash: ff828e927fa6d59e2e3597a1d2246eb2f2a625bfbc125dda6d6a5900ddf6031d

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/refactor-tool-system/proposal.md

- Source: openspec/changes/refactor-tool-system/proposal.md
- Lines: 1-33
- SHA256: 134ba78c24136f13d2de9cde14abd2fd0823e31790126245062cc19ffc603df6

```md
## Why

当前工具系统有三个核心问题：(1) 添加新工具需修改 3 个文件（Tool 类、main.py 注册、nodes.py 的 prompt），不具备可扩展性；(2) 缺少代码执行沙箱，Agent 无法进行数据分析、图表预处理等计算密集型操作；(3) ReAct 循环每次只能调用一个工具，数据收集阶段耗时长。这三个问题阻碍了 Winter Agent 向标准 AI Agent 平台演进。

## What Changes

- **标准化工具注册机制**：引入工具插件的自动发现与注册，添加新工具只需创建一个文件，无需修改其他代码
- **统一工具定义格式**：采用 OpenAI function/tool schema 作为工具描述标准，自动生成 LLM prompt，消除手动维护
- **代码执行沙箱**：支持 Agent 编写和执行 Python 代码，用于数据分析、图表数据预处理、文件处理等场景
- **并行工具调用**：单次 ReAct 迭代支持同时调用多个独立工具，减少数据收集阶段的往返次数
- **工具结果标准化**：统一工具返回格式，降低 LLM 理解不同工具结果的成本

## Capabilities

### New Capabilities

- `tool-auto-discovery`: 工具插件通过文件约定自动发现并注册到 ToolRegistry，无需手动在 main.py 注册
- `tool-schema-standard`: 统一的工具定义格式（OpenAI function schema），自动生成 LLM 系统提示词中的工具描述
- `code-sandbox`: 沙箱化的 Python 代码执行能力，支持数据分析、数据预处理、图表数据生成
- `parallel-tool-execution`: 单次 ReAct 迭代中并行调用多个无依赖关系的工具

### Modified Capabilities

<!-- 无已有 spec 需要修改 -->

## Impact

- **ai_service/tools/**：重构 BaseTool、ToolRegistry，新增 auto-discovery 和 schema 标准
- **ai_service/graph/nodes.py**：agent_node 工具调用协议从单工具 JSON 升级为支持并行调用的格式
- **ai_service/graph/graph.py**：可能需要新增并行执行节点或使用 LangGraph Send API
- **ai_service/main.py**：移除手动工具注册代码，改为自动发现
- **ai_service/tools/sandbox/**：新增代码沙箱工具模块
- **前端**：无需改动（工具调用过程对前端透明）
```

## openspec/changes/refactor-tool-system/design.md

- Source: openspec/changes/refactor-tool-system/design.md
- Lines: 1-134
- SHA256: 982e421993ce8060822b4e3674812119b9cd2edcadcd996c2eb1efabcba65c88

[TRUNCATED]

```md
## Context

当前工具系统架构：`BaseTool` (ABC) → 具体 Tool 类 → `main.py` 手动注册到 `ToolRegistry` → `agent_node` 硬编码 prompt 描述工具。添加一个工具需改动 3 个文件，工具结果格式不统一。ReAct 循环单次只能调用一个工具。

## Goals / Non-Goals

**Goals:**
- 工具插件式注册：创建单个文件即完成工具接入，自动发现 + 自动注册
- 统一工具定义格式（OpenAI function schema），自动生成 LLM 工具描述
- Python 代码执行沙箱，支持数据分析类工具调用
- 单次 ReAct 迭代可并行调用多个独立工具

**Non-Goals:**
- 不做可视化工具编排界面
- 不添加具体业务工具（数据库查询、文件上传等）
- 不做多 Agent 协作

## Decisions

### 1. 工具注册：文件约定自动发现 + 装饰器注册

**方案**：每个工具文件放置在 `tools/` 目录下，工具类使用 `@tool` 装饰器标记，`ToolRegistry` 在启动时扫描 `tools/` 目录自动发现并注册。

```python
# tools/search/tool.py
from tools.base import tool, BaseTool, ToolSchema

@tool
class SearchTool(BaseTool):
    name = "search"
    description = "Web search via Tavily API"
    schema = ToolSchema(
        parameters={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            }
        }
    )

    async def execute(self, input: dict) -> ToolResult:
        ...
```

**替代方案**：
- 配置注册（YAML/JSON）：更灵活但增加维护负担
- 手工注册（当前方案）：简单但不可扩展

**选择理由**：装饰器方案改动最小，符合 Python 惯例，`main.py` 无需修改。

### 2. 工具 Schema 标准化：OpenAI function schema

**方案**：`BaseTool` 新增 `schema: ToolSchema` 字段，使用 OpenAI function/tool 定义格式。`agent_node` 从 `ToolRegistry.list_tools()` 获取 schema 列表，注入到 JSON Mode prompt 中。

```python
class ToolSchema(BaseModel):
    parameters: dict  # JSON Schema for tool input

class BaseTool(ABC):
    name: str
    description: str
    schema: ToolSchema

    @abstractmethod
    async def execute(self, input: dict) -> ToolResult: ...
```

**选择理由**：OpenAI function schema 是最广泛使用的工具定义标准，DeepSeek/Claude/GPT 均兼容，未来迁移到 native function calling 时无需改写。

### 3. 并行工具调用协议

**方案**：`agent_node` JSON 输出从单工具格式升级为支持多工具：

```json
// 当前
{"action":"tool","tool":"search","query":"..."}

// 新：单工具（兼容）
{"action":"tool","tool":"search","query":"..."}
```

Full source: openspec/changes/refactor-tool-system/design.md

## openspec/changes/refactor-tool-system/tasks.md

- Source: openspec/changes/refactor-tool-system/tasks.md
- Lines: 1-36
- SHA256: 59161d0a784ddce804cae53c4b506579b87b6724601092d8f885bf4d13844c1c

```md
# Tasks: refactor-tool-system

## Phase 1: Tool Registry Foundation

- [ ] **Task 1: Add ToolSchema model and @tool decorator**
  Create `ai_service/tools/schema.py` with `ToolSchema` (OpenAI function schema) and `@tool` decorator that marks classes for auto-discovery. Tests: verify decorator sets metadata, schema validation.

- [ ] **Task 2: Rewrite ToolRegistry with auto-discovery**
  Refactor `ToolRegistry` to scan `tools/` directory at startup, discover `@tool`-decorated classes, validate schemas, and auto-register. Add `build_tools_prompt()` to generate LLM tool descriptions from schemas. Tests: mock filesystem scan, verify discovery and prompt generation.

- [ ] **Task 3: Migrate existing tools to @tool format**
  Update `SearchTool`, `BrowserUseTool`, `TimeTool` to use `@tool` decorator and `ToolSchema`. Remove manual registration from `main.py`. Tests: update existing tool tests.

## Phase 2: Parallel Tool Execution

- [ ] **Task 4: Update agent_node for parallel tool protocol**
  Support both `{"action":"tool",...}` (legacy) and `{"actions":[...]}` (parallel) formats. Max 3 parallel tools. Tests: single tool, 2 parallel, 3 parallel, >3 limit rejection.

- [ ] **Task 5: Update tool_node for parallel execution**
  Use `asyncio.gather()` when `actions` array present. Ensure error isolation (one failure doesn't block others). Tests: parallel success, mixed success/error, all error.

## Phase 3: Code Sandbox

- [ ] **Task 6: Create Docker sandbox for Python execution**
  Create `ai_service/tools/sandbox/` with `docker-compose.sandbox.yml` (python:3.12-slim with pandas/numpy/matplotlib), `CodeSandboxTool` using `@tool` decorator. Network disabled, CPU 1, memory 256M, timeout 30s. Tests: successful execution, timeout, error handling.

## Phase 4: Cleanup & Integration

- [ ] **Task 7: Remove manual tool registration from main.py**
  `main.py` now only needs `get_tool_registry()` — auto-discovery handles the rest. Verify startup logs show discovered tools.

- [ ] **Task 8: End-to-end integration test**
  Full flow: startup auto-discovers tools → agent uses parallel search → sandbox executes Python → result flows to chart planner. Verify all 3 phases of the pipeline work with new tool system.

- [ ] **Task 9: Update documentation**
  Add `ai_service/tools/README.md` explaining how to create a new tool with `@tool` decorator, schema format, and registration process.
```

## openspec/changes/refactor-tool-system/specs/code-sandbox/spec.md

- Source: openspec/changes/refactor-tool-system/specs/code-sandbox/spec.md
- Lines: 1-27
- SHA256: 0d997b51ae6b681342c1e0de7f121d31b0498e1e09d1faa0cfad66eb75865b02

```md
## ADDED Requirements

### Requirement: Agent can execute Python code in sandbox
The system SHALL provide an `execute_python` tool that runs Python code in an isolated Docker container. The container MUST have network access disabled, CPU limited to 1 core, memory limited to 256MB, and a 30-second default timeout.

#### Scenario: Execute data analysis code
- **WHEN** the agent calls `execute_python` with valid Python code that computes a result
- **THEN** the sandbox returns stdout output within the timeout period

#### Scenario: Timeout handling
- **WHEN** Python code execution exceeds the timeout (default 30s)
- **THEN** the container is forcefully terminated and the tool returns an error with code `TIMEOUT`

#### Scenario: Malicious code isolation
- **WHEN** the agent attempts to execute code that accesses the filesystem outside the sandbox directory
- **THEN** the operation is blocked by Docker container isolation and the process fails safely

### Requirement: Sandbox supports pip packages
The sandbox SHALL pre-install common data analysis packages (`pandas`, `numpy`, `matplotlib`) and allow the agent to `pip install` additional packages during execution.

#### Scenario: Use pre-installed pandas
- **WHEN** the code uses `import pandas` without prior installation
- **THEN** pandas is available and functional

#### Scenario: Install additional package
- **WHEN** the code includes `pip install requests` before using it
- **THEN** the package is installed and usable within the same execution session
```

## openspec/changes/refactor-tool-system/specs/parallel-tool-execution/spec.md

- Source: openspec/changes/refactor-tool-system/specs/parallel-tool-execution/spec.md
- Lines: 1-26
- SHA256: 921cfcdad70a5c11c8075a105c46f157d0c3a0f2e33505a3b8dc3cb78ab13bb1

```md
## ADDED Requirements

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
```

## openspec/changes/refactor-tool-system/specs/tool-auto-discovery/spec.md

- Source: openspec/changes/refactor-tool-system/specs/tool-auto-discovery/spec.md
- Lines: 1-23
- SHA256: 74756bec3d011ebdf138998b921c0a8a6ad89ea069cf0bcb3fa28fa8a303754f

```md
## ADDED Requirements

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
```

## openspec/changes/refactor-tool-system/specs/tool-schema-standard/spec.md

- Source: openspec/changes/refactor-tool-system/specs/tool-schema-standard/spec.md
- Lines: 1-23
- SHA256: 559924c1b4651ff8e8ed7582a7dd1a5d39aad706dbdf9795ef79af78cadd2a1c

```md
## ADDED Requirements

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
```

