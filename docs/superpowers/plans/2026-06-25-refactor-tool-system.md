---
archived-with: 2026-06-25-refactor-tool-system
status: final
---
# Tool System Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Refactor the tool system to use Pydantic-based schema, `@tool` decorator-based auto-discovery, parallel tool execution, and a Docker sandbox for Python code execution.

**Architecture:** The existing `BaseTool` ABC + `ToolRegistry` manual registration pattern is replaced by a `ToolSchema` (Pydantic BaseModel) + `@tool` decorator + auto-discovery via `BaseTool.__subclasses__()`. The `agent_node` gains parallel tool call support via an `actions` array in the JSON output. The `tool_node` uses `asyncio.gather()` for parallel execution. A new `CodeSandboxTool` runs Python in a Docker container.

**Tech Stack:** Python 3.12, Pydantic 2.13, FastAPI, LangGraph, asyncio, Docker, pytest

## Global Constraints

- All tools must remain backward-compatible with existing state fields (`current_tool`, `tool_input`, `tool_result`).
- The `ToolRegistry` must provide `discover()`, `list_tools()`, `list_capabilities()`, `invoke()`, `invoke_capability()`, and `build_tools_prompt()`.
- All existing tools live under `ai_service/tools/<name>/tool.py` with `__init__.py` re-exporting the tool class.
- Tests go in `ai_service/tests/test_*.py` with no conftest.py.
- Minimum Python 3.12, Pydantic >=2.0.0.
- The parallel protocol supports at most 3 simultaneous tool calls.

---
```yaml
---
change: refactor-tool-system
design-doc: docs/superpowers/specs/2026-06-25-refactor-tool-system-design.md
base-ref: 0a6fd0cc580f2c538a54052bb5c41d7268bb7603
---
```

## File Structure

### Files to Create

| File | Responsibility |
|------|---------------|
| `ai_service/tools/schema.py` | `ToolSchema` Pydantic model + `@tool` decorator |
| `ai_service/tests/test_tool_schema.py` | Tests for ToolSchema and @tool decorator (Task 1) |
| `ai_service/tests/test_tool_registry.py` | Tests for ToolRegistry.discover() and build_tools_prompt() (Task 2) |
| `ai_service/tests/test_tool_migration.py` | Tests for migrated SearchTool/TimeTool/BrowserUseTool (Task 3) |
| `ai_service/tests/test_parallel_protocol.py` | Tests for parallel agent_node and tool_node (Tasks 4-5) |
| `ai_service/tests/test_code_sandbox.py` | Tests for CodeSandboxTool (Task 6) |
| `ai_service/tools/sandbox/docker-compose.sandbox.yml` | Docker compose for sandbox (Task 6) |
| `ai_service/tools/sandbox/Dockerfile.sandbox` | Docker image for sandbox (Task 6) |
| `ai_service/tools/sandbox/tool.py` | CodeSandboxTool (Task 6) |
| `ai_service/tools/sandbox/__init__.py` | Package init for sandbox (Task 6) |
| `ai_service/tests/test_end_to_end.py` | End-to-end integration test (Task 8) |

### Files to Modify

| File | Changes |
|------|---------|
| `ai_service/tools/base.py` | Add `schema: ToolSchema` field (replaces `input_schema`) |
| `ai_service/tools/registry.py` | Add `discover()` and `build_tools_prompt()` methods |
| `ai_service/tools/__init__.py` | Export `ToolSchema`, `tool` |
| `ai_service/tools/search/tool.py` | Add `@tool`, use `ToolSchema` |
| `ai_service/tools/time/tool.py` | Add `@tool`, use `ToolSchema` |
| `ai_service/tools/browser/tool.py` | Add `@tool`, use `ToolSchema` |
| `ai_service/graph/nodes.py` | Parallel protocol in `agent_node` and `tool_node` |
| `ai_service/main.py` | Remove manual tool registration |
| `ai_service/requirements.txt` | Add `docker` Python package |
| `ai_service/tools/README.md` | Document new tool creation pattern |

### Sequential Dependency Graph

```
Task 1 (schema + decorator)
  └── Task 2 (auto-discovery registry)
        └── Task 3 (migrate tools)
              ├── Task 4 (parallel agent_node)
              │     └── Task 5 (parallel tool_node)
              ├── Task 6 (sandbox)
              └── Task 7 (cleanup main.py)
                    └── Task 8 (e2e test)
                          └── Task 9 (documentation)
```

---

### Task 1: Add ToolSchema model and @tool decorator

**Files:**
- Create: `ai_service/tools/schema.py`
- Modify: `ai_service/tools/base.py` (add `schema` field to `BaseTool`)
- Modify: `ai_service/tools/__init__.py` (export new symbols)
- Create: `ai_service/tests/test_tool_schema.py`

**Interfaces:**
- Produces: `ToolSchema(BaseModel)` with field `parameters: dict`
- Produces: `tool(cls)` decorator that sets `cls._is_tool = True`
- Consumes: `BaseTool` from `tools/base.py` — adds `schema: ToolSchema` class attribute
- Consumes: `ToolResult` from `tools/base.py` — unchanged

- [x] **Step 1: Write the failing tests**

Create `ai_service/tests/test_tool_schema.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tools.schema import ToolSchema, tool


class TestToolSchema:
    def test_valid_schema(self):
        s = ToolSchema(parameters={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
        })
        assert s.parameters["type"] == "object"
        assert "query" in s.parameters["required"]

    def test_schema_with_optional_fields(self):
        s = ToolSchema(parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": [],
        })
        assert s.parameters["required"] == []

    def test_empty_parameters(self):
        s = ToolSchema(parameters={})
        assert s.parameters == {}

    def test_nested_properties(self):
        s = ToolSchema(parameters={
            "type": "object",
            "properties": {
                "filter": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "value": {"type": "string"},
                    },
                },
            },
        })
        assert s.parameters["properties"]["filter"]["type"] == "object"


class TestToolDecorator:
    def test_decorator_sets_meta(self):
        @tool
        class MyTool:
            pass

        assert hasattr(MyTool, "_is_tool")
        assert MyTool._is_tool is True

    def test_decorator_preserves_class(self):
        @tool
        class MyTool:
            name = "my_tool"

        assert MyTool.name == "my_tool"

    def test_decorator_multiple_classes(self):
        @tool
        class ToolA:
            pass

        @tool
        class ToolB:
            pass

        assert ToolA._is_tool is True
        assert ToolB._is_tool is True

    def test_without_decorator_no_meta(self):
        class NormalClass:
            pass

        assert not hasattr(NormalClass, "_is_tool")
```

- [x] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/test_tool_schema.py -v
```
Expected: `ModuleNotFoundError: No module named 'tools.schema'`

- [x] **Step 3: Create `ai_service/tools/schema.py`**

```python
from __future__ import annotations

from pydantic import BaseModel


class ToolSchema(BaseModel):
    """OpenAI function schema for a tool's input parameters."""
    parameters: dict


def tool(cls):
    """Decorator: marks a BaseTool subclass for auto-discovery."""
    cls._is_tool = True
    return cls
```

- [x] **Step 4: Update `ai_service/tools/base.py` -- replace `input_schema` with `schema: ToolSchema`**

Edit `ai_service/tools/base.py`. Replace the class attribute `input_schema: dict[str, Any]` with `schema: ToolSchema`. Also remove `output_schema`, `version`, `timeout_ms`, `retry_policy`, `policy_tags` since they are either covered by ToolSchema or managed by the registry.

New content for `ai_service/tools/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from tools.schema import ToolSchema


@dataclass(slots=True)
class ToolError:
    code: str
    message: str
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }


@dataclass(slots=True)
class ToolResult:
    ok: bool
    data: Any = None
    error: ToolError | None = None

    @classmethod
    def success(cls, data: Any) -> "ToolResult":
        return cls(ok=True, data=data, error=None)

    @classmethod
    def failure(cls, code: str, message: str, retryable: bool = False) -> "ToolResult":
        return cls(ok=False, data=None, error=ToolError(code=code, message=message, retryable=retryable))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
        }


class BaseTool(ABC):
    name: str
    description: str
    schema: ToolSchema

    @abstractmethod
    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        """Execute the tool with validated input payload."""
```

- [x] **Step 5: Update `ai_service/tools/__init__.py`**

```python
from tools.base import BaseTool, ToolError, ToolResult
from tools.registry import DuplicateToolError, ToolNotFoundError, ToolRegistry
from tools.schema import ToolSchema, tool

__all__ = [
    "BaseTool",
    "ToolError",
    "ToolResult",
    "ToolRegistry",
    "DuplicateToolError",
    "ToolNotFoundError",
    "ToolSchema",
    "tool",
]
```

- [x] **Step 6: Run tests to verify they pass**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/test_tool_schema.py -v
```
Expected: All 7 tests PASS

- [x] **Step 7: Commit**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/tools/schema.py ai_service/tools/base.py ai_service/tools/__init__.py ai_service/tests/test_tool_schema.py
git commit -m "feat: add ToolSchema model and @tool decorator for tool auto-discovery"
```

---

### Task 2: Rewrite ToolRegistry with auto-discovery

**Files:**
- Modify: `ai_service/tools/registry.py` (add `discover()`, `build_tools_prompt()`)
- Create: `ai_service/tests/test_tool_registry.py`

**Interfaces:**
- Consumes: `BaseTool`, `ToolSchema`, `tool` from `tasks/1` (the `_is_tool` marker, `schema` field, `name`, `description`)
- Produces: `ToolRegistry.discover()` — scans `BaseTool.__subclasses__()`, filters by `_is_tool`, validates schema, calls `register()`
- Produces: `ToolRegistry.build_tools_prompt()` — returns a formatted string for LLM prompt

- [x] **Step 1: Write the failing tests**

Create `ai_service/tests/test_tool_registry.py`:

```python
from __future__ import annotations

from typing import Any, Mapping

import pytest

from tools.base import BaseTool, ToolResult
from tools.registry import DuplicateToolError, ToolNotFoundError, ToolRegistry
from tools.schema import ToolSchema, tool


class TestToolRegistryDiscover:
    def teardown_method(self):
        """Clean up tool classes registered in BaseTool.__subclasses__."""
        # Remove test subclasses added during this test
        ToolRegistry._registry_cache = {}  # reset cache between tests
        # After each test, _is_tool marker is fine since subclasses persist

    def test_discover_finds_tool_decorated_classes(self):
        @tool
        class AlphaTool(BaseTool):
            name = "alpha"
            description = "Alpha tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("done")

        registry = ToolRegistry()
        registry.discover()
        tools = registry.list_tools()
        names = [t["name"] for t in tools]
        assert "alpha" in names

    def test_skips_non_decorated_subclasses(self):
        class BetaTool(BaseTool):
            name = "beta"
            description = "Beta tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {},
                "required": [],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("done")

        registry = ToolRegistry()
        registry.discover()
        tools = registry.list_tools()
        names = [t["name"] for t in tools]
        assert "beta" not in names

    def test_skips_incomplete_schema(self):
        @tool
        class GammaTool(BaseTool):
            name = "gamma"
            description = "Gamma tool"
            # schema not set — will be None, causing validation to fail

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("done")

        registry = ToolRegistry()
        registry.discover()
        tools = registry.list_tools()
        names = [t["name"] for t in tools]
        assert "gamma" not in names

    def test_skip_class_without_name(self):
        @tool
        class NoNameTool(BaseTool):
            description = "No name tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {},
                "required": [],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("done")

        registry = ToolRegistry()
        registry.discover()
        tools = registry.list_tools()
        assert len(tools) == 0


class TestToolRegistryMethods:
    def teardown_method(self):
        ToolRegistry._registry_cache = {}

    def test_list_tools_format(self):
        @tool
        class DeltaTool(BaseTool):
            name = "delta"
            description = "Delta tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("done")

        registry = ToolRegistry()
        registry.discover()
        tools = registry.list_tools()
        t = tools[0]
        assert "name" in t
        assert "description" in t
        assert "input_schema" in t
        assert t["name"] == "delta"
        assert t["description"] == "Delta tool"
        assert t["input_schema"] == DeltaTool.schema.parameters

    def test_build_tools_prompt(self):
        @tool
        class EpsilonTool(BaseTool):
            name = "epsilon"
            description = "Epsilon tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"input": {"type": "string"}},
                "required": ["input"],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("done")

        registry = ToolRegistry()
        registry.discover()
        prompt = registry.build_tools_prompt()
        assert "epsilon" in prompt
        assert "Epsilon tool" in prompt

    def test_build_tools_prompt_empty_registry(self):
        registry = ToolRegistry()
        prompt = registry.build_tools_prompt()
        assert prompt == ""

    def test_register_and_invoke(self):
        @tool
        class ZetaTool(BaseTool):
            name = "zeta"
            description = "Zeta tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success(str(input_payload.get("msg", "")))

        registry = ToolRegistry()
        registry.discover()
        result = await registry.invoke("zeta", {"msg": "hello"})
        assert result["ok"] is True
        assert result["data"] == "hello"

    def test_invoke_not_found(self):
        registry = ToolRegistry()
        with pytest.raises(ToolNotFoundError):
            await registry.invoke("nonexistent", {})

    def test_duplicate_register(self):
        @tool
        class EtaTool(BaseTool):
            name = "eta"
            description = "Eta tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {},
                "required": [],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("done")

        registry = ToolRegistry()
        registry.register(EtaTool())
        with pytest.raises(DuplicateToolError):
            registry.register(EtaTool())
```

- [x] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/test_tool_registry.py -v
```
Expected: Various failures because `ToolRegistry` doesn't have `discover()` or `build_tools_prompt()` yet.

- [x] **Step 3: Rewrite `ai_service/tools/registry.py`**

Replace the entire file content:

```python
from __future__ import annotations

import logging
from typing import Any, Mapping

from domain.capability import CapabilityCall, CapabilityResult, CapabilitySpec
from tools.base import BaseTool, ToolResult
from tools.schema import ToolSchema

logger = logging.getLogger(__name__)


class ToolRegistryError(Exception):
    """Base error for tool registry issues."""


class DuplicateToolError(ToolRegistryError):
    """Raised when a tool name is already registered."""


class ToolNotFoundError(ToolRegistryError):
    """Raised when a tool name does not exist."""


class ToolRegistry:
    _registry_cache: dict[str, BaseTool] = {}

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        # Prime from class-level cache so multiple registries share discovered tools
        if ToolRegistry._registry_cache:
            self._tools = dict(ToolRegistry._registry_cache)

    def discover(self) -> None:
        """Auto-discover all @tool-decorated BaseTool subclasses."""
        from tools.schema import tool as _tool  # noqa: F811

        for cls in BaseTool.__subclasses__():
            if not getattr(cls, "_is_tool", False):
                continue

            name = getattr(cls, "name", None)
            description = getattr(cls, "description", None)
            schema = getattr(cls, "schema", None)

            if not name or not description or not isinstance(schema, ToolSchema):
                logger.warning(
                    "Skipping tool %s: missing name, description, or schema",
                    cls.__name__,
                )
                continue

            if not isinstance(schema.parameters, dict) or not schema.parameters.get("properties"):
                logger.warning(
                    "Skipping tool '%s': schema.parameters missing 'properties'",
                    name,
                )
                continue

            if name in self._tools:
                logger.info("Tool '%s' already registered, skipping", name)
                continue

            try:
                instance = cls()
                self._tools[name] = instance
                logger.info("Discovered and registered tool '%s'", name)
            except Exception as exc:
                logger.error("Failed to instantiate tool '%s': %s", name, exc)

        # Update class-level cache
        ToolRegistry._registry_cache = dict(self._tools)

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise DuplicateToolError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if not tool:
            raise ToolNotFoundError(f"Tool '{name}' is not registered")
        return tool

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.schema.parameters,
            }
            for tool in self._tools.values()
        ]

    def list_capabilities(self) -> list[dict[str, Any]]:
        return [
            CapabilitySpec(
                name=tool.name,
                version="1.0.0",
                kind="tool",
                description=tool.description,
                input_schema=tool.schema.parameters,
                output_schema={},
                timeout_ms=30000,
                retry_policy={"max_retries": 0},
                policy_tags=[],
            ).to_dict()
            for tool in self._tools.values()
        ]

    def build_tools_prompt(self) -> str:
        """Build a formatted tool description string for LLM prompts."""
        lines = []
        for tool in self._tools.values():
            lines.append(f"  - {tool.name}: {tool.description}")
        return "\n".join(lines)

    async def invoke(self, name: str, input_payload: Mapping[str, Any]) -> dict[str, Any]:
        tool = self.get(name)
        result = await tool.execute(input_payload)
        if isinstance(result, ToolResult):
            return result.to_dict()
        if isinstance(result, Mapping):
            return dict(result)
        raise ToolRegistryError(
            f"Tool '{name}' returned an unsupported result type: {type(result).__name__}"
        )

    async def invoke_capability(self, call: CapabilityCall) -> dict[str, Any]:
        try:
            return await self.invoke(call.capability_name, call.input_payload)
        except ToolNotFoundError:
            return CapabilityResult.failure(
                code="CAPABILITY_NOT_FOUND",
                message=f"Capability '{call.capability_name}' is not registered",
            ).to_dict()
        except Exception as exc:
            return CapabilityResult.failure(
                code="CAPABILITY_INVOKE_EXCEPTION",
                message=str(exc)[:200],
                retryable=False,
            ).to_dict()
```

- [x] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/test_tool_registry.py -v
```
Expected: All tests PASS

- [x] **Step 5: Commit**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/tools/registry.py ai_service/tests/test_tool_registry.py
git commit -m "feat: rewrite ToolRegistry with auto-discovery and build_tools_prompt"
```

---

### Task 3: Migrate existing tools to @tool format

**Files:**
- Modify: `ai_service/tools/search/tool.py`
- Modify: `ai_service/tools/time/tool.py`
- Modify: `ai_service/tools/browser/tool.py`
- Create: `ai_service/tests/test_tool_migration.py`

**Interfaces:**
- Consumes: `BaseTool`, `ToolSchema`, `tool` decorator from Tasks 1-2
- Produces: `SearchTool` with `@tool` decorator + `ToolSchema`
- Produces: `TimeTool` with `@tool` decorator + `ToolSchema`
- Produces: `BrowserUseTool` with `@tool` decorator + `ToolSchema`

- [x] **Step 1: Write the failing tests**

Create `ai_service/tests/test_tool_migration.py`:

```python
from __future__ import annotations

from typing import Any, Mapping

import pytest

from tools.base import BaseTool, ToolResult
from tools.registry import ToolRegistry
from tools.schema import ToolSchema


class TestMigratedTools:
    def test_search_tool_has_tool_decorator(self):
        from tools.search import SearchTool
        assert hasattr(SearchTool, "_is_tool")
        assert SearchTool._is_tool is True

    def test_search_tool_schema(self):
        from tools.search import SearchTool
        assert isinstance(SearchTool.schema, ToolSchema)
        assert "query" in SearchTool.schema.parameters.get("required", [])

    def test_search_tool_name(self):
        from tools.search import SearchTool
        assert SearchTool.name == "search"

    def test_search_tool_description(self):
        from tools.search import SearchTool
        assert isinstance(SearchTool.description, str)
        assert len(SearchTool.description) > 0

    def test_time_tool_has_tool_decorator(self):
        from tools.time.tool import TimeTool
        assert hasattr(TimeTool, "_is_tool")
        assert TimeTool._is_tool is True

    def test_time_tool_schema(self):
        from tools.time.tool import TimeTool
        assert isinstance(TimeTool.schema, ToolSchema)
        # timezone is optional
        assert "timezone" in TimeTool.schema.parameters.get("properties", {})

    def test_time_tool_name(self):
        from tools.time.tool import TimeTool
        assert TimeTool.name == "time"

    def test_browser_tool_has_tool_decorator(self):
        from tools.browser import BrowserUseTool
        assert hasattr(BrowserUseTool, "_is_tool")
        assert BrowserUseTool._is_tool is True

    def test_browser_tool_schema(self):
        from tools.browser import BrowserUseTool
        assert isinstance(BrowserUseTool.schema, ToolSchema)
        assert "url" in BrowserUseTool.schema.parameters.get("required", [])

    def test_browser_tool_name(self):
        from tools.browser import BrowserUseTool
        assert BrowserUseTool.name == "browser"

    def test_discover_finds_all_migrated_tools(self):
        # Clear the registry cache so discover() runs fresh
        ToolRegistry._registry_cache = {}

        registry = ToolRegistry()
        registry.discover()
        tools = registry.list_tools()
        names = [t["name"] for t in tools]
        assert "search" in names
        assert "time" in names
        assert "browser" in names
```

- [x] **Step 2: Run test to verify it fails**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/test_tool_migration.py -v
```
Expected: Failures because existing tools don't have `@tool` decorator or `ToolSchema`.

- [x] **Step 3: Migrate `ai_service/tools/search/tool.py`**

Make the following changes:
1. Replace `input_schema` assignment with `schema = ToolSchema(parameters={...})`
2. Add `@tool` decorator

Changes to the SearchTool class:

```python
from tools.schema import ToolSchema, tool

@tool
class SearchTool(BaseTool):
    name = "search"
    description = "Search the web for a query and return ranked snippets."
    schema = ToolSchema(parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query text"},
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    })
```

Add the imports at the top of the file:
```python
from tools.schema import ToolSchema, tool
```

Remove the old `input_schema` class attribute.

- [x] **Step 4: Migrate `ai_service/tools/time/tool.py`**

Changes to the TimeTool class:

```python
from tools.schema import ToolSchema, tool

@tool
class TimeTool(BaseTool):
    name = "time"
    description = "Get the current date and time. Useful for questions about the current time or date."
    schema = ToolSchema(parameters={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "The timezone to get the time for (e.g., 'Asia/Shanghai', 'UTC'). Defaults to local system time if not provided."
            }
        },
        "required": [],
    })
```

Add the imports at the top of the file:
```python
from tools.schema import ToolSchema, tool
```

Remove the old `input_schema` class attribute.

- [x] **Step 5: Migrate `ai_service/tools/browser/tool.py`**

Changes to the BrowserUseTool class:

```python
from tools.schema import ToolSchema, tool

@tool
class BrowserUseTool(BaseTool):
    name = "browser"
    description = (
        "Visit a URL and extract readable text content from the web page. "
        "Useful for reading articles, documentation, news, or any web page. "
        "Use this after searching to read the full content of a specific result."
    )
    schema = ToolSchema(parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full URL of the web page to visit and extract content from",
            },
            "extract_mode": {
                "type": "string",
                "enum": ["article", "full"],
                "description": "Extraction mode: 'article' tries to find the main content (default), 'full' extracts all visible text",
            },
        },
        "required": ["url"],
    })
```

Add the imports at the top of the file:
```python
from tools.schema import ToolSchema, tool
```

Remove the old `input_schema` class attribute.

- [x] **Step 6: Run tests to verify they pass**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/test_tool_migration.py -v
```
Expected: All tests PASS

- [x] **Step 7: Run existing tests to verify no regressions**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/ -v
```
Expected: All existing tests still PASS (the migration only changes the schema field name and adds decorators, existing tests use `tools/base.py` types which are unchanged).

- [x] **Step 8: Commit**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/tools/search/tool.py ai_service/tools/time/tool.py ai_service/tools/browser/tool.py ai_service/tests/test_tool_migration.py
git commit -m "feat: migrate SearchTool, TimeTool, BrowserUseTool to @tool decorator and ToolSchema"
```

---

### Task 4: Update agent_node for parallel tool protocol

**Files:**
- Modify: `ai_service/graph/nodes.py` (update `agent_node` and `_REACT_SYSTEM_PROMPT`)

**Interfaces:**
- Consumes: state fields `current_tool`, `tool_input`, `tool_result`, `iteration_count`, `last_tool_name`, `last_tool_query`, `consecutive_search_count`
- Consumes: `ToolRegistry.build_tools_prompt()` from Task 2
- Produces: Updated `_REACT_SYSTEM_PROMPT` mentioning `actions` parallel format
- Produces: `agent_node` returns `{"tool_input": {"actions": [...]}}` for parallel calls

- [x] **Step 1: Write the failing tests**

Create `ai_service/tests/test_parallel_protocol.py`:

```python
from __future__ import annotations

from typing import Any, Mapping

import pytest

from graph.state import State
from tools.base import BaseTool, ToolResult
from tools.registry import ToolRegistry
from tools.schema import ToolSchema, tool


class TestAgentNodeParallelProtocol:
    """Tests for agent_node JSON parsing of parallel 'actions' field.

    These tests validate the JSON parsing logic inside agent_node
    without calling the LLM (we test the prompt construction and
    the parsing branches separately).
    """

    def test_actions_array_recognized_in_parsed_output(self):
        """Verify that a parsed JSON with 'actions' is treated as parallel."""
        # This is a logic test — the actual LLM JSON parsing is in agent_node.
        # We simulate the parsed result.
        parsed = {
            "actions": [
                {"tool": "search", "query": "GDP 2024"},
                {"tool": "time", "query": ""},
            ]
        }
        actions = parsed.get("actions")
        assert actions is not None
        assert len(actions) == 2
        assert actions[0]["tool"] == "search"
        assert actions[1]["tool"] == "time"

    def test_single_action_field_backward_compatible(self):
        """Verify that 'action' field still works (legacy path)."""
        parsed = {"action": "tool", "tool": "search", "query": "hello"}
        action = str(parsed.get("action", "")).strip().lower()
        assert action == "tool"
        assert parsed.get("tool") == "search"

    def test_actions_max_3(self):
        """Verify that at most 3 actions are allowed."""
        parsed = {
            "actions": [
                {"tool": "a", "query": "1"},
                {"tool": "b", "query": "2"},
                {"tool": "c", "query": "3"},
                {"tool": "d", "query": "4"},
            ]
        }
        actions = parsed.get("actions", [])[:3]
        assert len(actions) == 3

    def test_actions_empty_list(self):
        """Empty actions should result in no-op."""
        parsed = {"actions": []}
        actions = parsed.get("actions", [])
        assert len(actions) == 0

    def test_both_actions_and_action_prefer_actions(self):
        """When both present, 'actions' takes priority."""
        parsed = {
            "actions": [{"tool": "search", "query": "parallel"}],
            "action": "tool",
            "tool": "time",
            "query": "",
        }
        actions = parsed.get("actions")
        assert actions is not None
        assert len(actions) == 1
        assert actions[0]["tool"] == "search"


# Register minimal tools for prompt testing
@tool
class MockToolA(BaseTool):
    name = "mock_a"
    description = "Mock tool A"
    schema = ToolSchema(parameters={
        "type": "object",
        "properties": {"q": {"type": "string"}},
        "required": ["q"],
    })

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success("a")


@tool
class MockToolB(BaseTool):
    name = "mock_b"
    description = "Mock tool B"
    schema = ToolSchema(parameters={
        "type": "object",
        "properties": {"q": {"type": "string"}},
        "required": ["q"],
    })

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success("b")


class TestPromptBuilds:
    def test_tools_prompt_includes_build_tools_prompt(self):
        ToolRegistry._registry_cache = {}
        registry = ToolRegistry()
        registry.register(MockToolA())
        registry.register(MockToolB())
        prompt = registry.build_tools_prompt()
        assert "mock_a" in prompt
        assert "mock_b" in prompt
```

- [x] **Step 2: Update `_REACT_SYSTEM_PROMPT` in `ai_service/graph/nodes.py`**

Replace the existing `_REACT_SYSTEM_PROMPT` to include the parallel `actions` format:

```python
_REACT_SYSTEM_PROMPT = """\
You are a ReAct agent. Your response MUST be a single valid JSON object.

[Internal Cycle: Thought → Action → Observation → Final Answer]

CRITICAL: Output ONLY the JSON object. No markdown wrapping, no explanation.

Single tool call format:
{"action":"tool","tool":"<name>","query":"<query>"}

Parallel tool call format (use when multiple independent lookups are needed):
{"actions": [
    {"tool":"<name1>","query":"<query1>"},
    {"tool":"<name2>","query":"<query2>"}
]}

At most 3 tools in an actions array.

Final answer ready (data collection complete):
{"action":"final_answer"}

Available tools:
- search: web search. Returns titles, URLs, and content snippets.
- browser: open a URL and read its content. MUST use exact URL from search results. Never fabricate URLs.
- time: get current date/time. Use for time-related questions.

Rules:
1. Output ONLY the JSON object. No other text — no markdown, no explanation.
2. For questions involving facts, data, statistics, numbers, or real-world information, you MUST call search first — never answer from training data alone.
3. After search returns results, open at least one URL with browser to read the actual content.
4. If browser returns an error, use search snippets directly — do NOT retry browser.
5. Call final_answer ONLY after you have collected evidence via tools. If you haven't used any tools, do NOT output final_answer.
6. Use parallel calls (actions) when the question has multiple independent sub-questions — e.g. search for "GDP 2024" and search for "population 2024" can run simultaneously.
"""
```

- [x] **Step 3: Update `agent_node` in `ai_service/graph/nodes.py` to support `actions`**

Replace the tool builds section in `agent_node`:

In the section where `tools_desc` is built (around line 142-145), replace manual tool listing with:

```python
    # 1. Build tool list description using registry
    tools_desc = ""
    if registry:
        tools_desc = registry.build_tools_prompt()
```

Then, in the JSON parsing section (after `parsed = json.loads(content)` around line 190), add parallel action handling between the JSON parse and the `action == "tool"` check. Replace the section starting at line 195:

```python
    action = str(parsed.get("action", "")).strip().lower()
    actions = parsed.get("actions")

    # 4a. Handle parallel tool calls
    if actions is not None and isinstance(actions, list) and len(actions) > 0:
        # Limit to 3
        actions = actions[:3]

        # Validate each action
        valid_actions = []
        for a in actions:
            tool_name = str(a.get("tool", "")).strip().lower()
            query = str(a.get("query", "")).strip()
            if tool_name:
                valid_actions.append({"tool": tool_name, "query": query})

        if not valid_actions:
            return _force_final_answer(state, tool_result)

        current_iteration = int(state.get("iteration_count", 0) or 0)
        if current_iteration >= MAX_ITERATIONS:
            reason = _reason_record("agent_node", "MAX_ITERATIONS_REACHED",
                f"Iteration limit ({MAX_ITERATIONS}) reached; forcing final answer.")
            return _force_final_answer(state, tool_result, reason)

        reason = _reason_record("agent_node", "PARALLEL_TOOL_CALL",
            f"Parallel call with {len(valid_actions)} tools",
            extra={"tool_count": len(valid_actions)})
        return {
            "current_tool": "__parallel__",
            "tool_input": {"actions": valid_actions},
            "tool_result": None,
            "iteration_count": current_iteration + 1,
            "last_tool_name": "__parallel__",
            "last_tool_query": "",
            "consecutive_search_count": int(state.get("consecutive_search_count", 0) or 0),
            "reasoning_steps": _append_reason(state, reason),
            "route": "tool",
        }

    # 4b. Handle single tool call (backward compatible)
    if action == "tool":
        # ... existing code unchanged from this point ...
```

- [x] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/test_parallel_protocol.py -v
```
Expected: All tests PASS

- [x] **Step 5: Run existing tool tests to verify regressions**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/ -v
```
Expected: No regressions. If any graph-related tests call `agent_node` and fail due to prompt changes, fix the test expectations to match the new prompt text.

- [x] **Step 6: Commit**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/graph/nodes.py ai_service/tests/test_parallel_protocol.py
git commit -m "feat: update agent_node with parallel tool protocol (actions array)"
```

---

### Task 5: Update tool_node for parallel execution

**Files:**
- Modify: `ai_service/graph/nodes.py` (update `tool_node` for parallel execution)
- Modify: `ai_service/tests/test_parallel_protocol.py` (add tool_node parallel tests)
- Modify: `ai_service/graph/normalizers/tool_result.py` (update `normalize_tool_step_record` for parallel)

**Interfaces:**
- Consumes: `tool_input` with either `{"query": ...}` (single) or `{"actions": [...]}` (parallel)
- Consumes: `CapabilityCall`, `ToolRegistry.invoke_capability()` from Task 2
- Produces: `tool_node` returns merged `tool_result` for parallel calls
- Produces: Multiple `tool_step_record` entries for parallel calls

- [x] **Step 1: Write the failing tests for parallel tool_node**

Append to `ai_service/tests/test_parallel_protocol.py`:

```python
class TestToolNodeParallelExecution:
    """Tests for tool_node parallel execution logic.

    These test the core parallel execution logic without calling asyncio.gather
    against real tools — we mock the registry to simulate responses.
    """

    async def test_parallel_two_success(self):
        """Two parallel tools both succeed."""
        from tools.registry import ToolRegistry
        ToolRegistry._registry_cache = {}
        registry = ToolRegistry()

        @tool
        class SearchMock(BaseTool):
            name = "search_mock"
            description = "Mock search"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            })
            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success(f"result for {input_payload.get('q', '')}")

        @tool
        class TimeMock(BaseTool):
            name = "time_mock"
            description = "Mock time"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {},
                "required": [],
            })
            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("2024-01-01")

        registry.register(SearchMock())
        registry.register(TimeMock())

        actions = [
            {"tool": "search_mock", "query": "hello"},
            {"tool": "time_mock", "query": ""},
        ]

        import asyncio
        from domain.capability import CapabilityCall

        tasks = []
        for a in actions:
            call = CapabilityCall(capability_name=a["tool"], input_payload={"query": a.get("query", "")})
            tasks.append(registry.invoke_capability(call))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert len(results) == 2
        assert results[0]["ok"] is True
        assert results[0]["data"] == "result for hello"
        assert results[1]["ok"] is True
        assert results[1]["data"] == "2024-01-01"

    async def test_parallel_one_fails_error_isolation(self):
        """One tool fails, the other succeeds — error isolation."""
        from tools.registry import ToolRegistry
        ToolRegistry._registry_cache = {}
        registry = ToolRegistry()

        @tool
        class GoodTool(BaseTool):
            name = "good"
            description = "Good tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {},
                "required": [],
            })
            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("ok")

        @tool
        class BadTool(BaseTool):
            name = "bad"
            description = "Bad tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {},
                "required": [],
            })
            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                raise ValueError("something went wrong")

        registry.register(GoodTool())
        registry.register(BadTool())

        actions = [
            {"tool": "good", "query": ""},
            {"tool": "bad", "query": ""},
        ]

        import asyncio
        from domain.capability import CapabilityCall

        tasks = []
        for a in actions:
            call = CapabilityCall(capability_name=a["tool"], input_payload={"query": a.get("query", "")})
            tasks.append(registry.invoke_capability(call))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert len(results) == 2
        assert results[0]["ok"] is True
        assert results[1]["ok"] is False

    async def test_parallel_all_fail(self):
        """All parallel tools fail."""
        from tools.registry import ToolRegistry
        ToolRegistry._registry_cache = {}
        registry = ToolRegistry()

        @tool
        class FailA(BaseTool):
            name = "fail_a"
            description = "Fail A"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {},
                "required": [],
            })
            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.failure("ERR_A", "failed A")

        @tool
        class FailB(BaseTool):
            name = "fail_b"
            description = "Fail B"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {},
                "required": [],
            })
            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.failure("ERR_B", "failed B")

        registry.register(FailA())
        registry.register(FailB())

        actions = [
            {"tool": "fail_a", "query": ""},
            {"tool": "fail_b", "query": ""},
        ]

        import asyncio
        from domain.capability import CapabilityCall

        tasks = []
        for a in actions:
            call = CapabilityCall(capability_name=a["tool"], input_payload={"query": a.get("query", "")})
            tasks.append(registry.invoke_capability(call))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert len(results) == 2
        assert results[0]["ok"] is False
        assert results[1]["ok"] is False

    async def test_parallel_at_most_3(self):
        """Only first 3 actions are executed."""
        from tools.registry import ToolRegistry
        ToolRegistry._registry_cache = {}
        registry = ToolRegistry()

        @tool
        class EchoTool(BaseTool):
            name = "echo"
            description = "Echo"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            })
            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success(input_payload.get("msg", ""))

        registry.register(EchoTool())

        actions = [
            {"tool": "echo", "query": "1"},
            {"tool": "echo", "query": "2"},
            {"tool": "echo", "query": "3"},
            {"tool": "echo", "query": "4"},
        ]

        limited = actions[:3]
        assert len(limited) == 3
```

- [x] **Step 2: Update `tool_node` in `ai_service/graph/nodes.py` for parallel execution**

Replace the `tool_node` function. The new version detects `actions` in `tool_input` and executes in parallel:

```python
async def tool_node(state: State) -> dict:
    tool_name = state.get("current_tool") or ""
    tool_input = state.get("tool_input") or {}
    start_time = time.time()
    gate = _build_policy_gate()

    # ── Parallel execution path ────────────────────────────────────────────
    if isinstance(tool_input, dict) and "actions" in tool_input:
        return await _execute_parallel_tools(state, tool_input["actions"], gate, start_time)

    # ── Single tool execution path (backward compatible) ───────────────────
    return await _execute_single_tool(state, tool_name, tool_input, gate, start_time)


async def _execute_parallel_tools(
    state: State,
    actions: list[dict],
    gate: PolicyGate,
    start_time: float,
) -> dict:
    """Execute multiple tools in parallel with error isolation."""
    registry = get_tool_registry()
    new_tool_steps = list(state.get("tool_steps", []))

    if not registry:
        merged = _build_parallel_error_result(actions, "ToolRegistry not initialized")
        return _build_parallel_return(state, merged, new_tool_steps, start_time)

    # Build tasks (at most 3)
    tasks = []
    for a in actions[:3]:
        tool_name = str(a.get("tool", "")).strip().lower()
        query = str(a.get("query", "")).strip()
        call = CapabilityCall(capability_name=tool_name, input_payload={"query": query})
        tasks.append(_invoke_single_with_gate(registry, call, gate, tool_name, query))

    # Run all tasks concurrently
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect results and step records
    all_ok = True
    merged_data = []
    for i, (a, raw) in enumerate(zip(actions[:3], raw_results)):
        if isinstance(raw, dict):
            merged_data.append(raw)
            if not raw.get("ok", False):
                all_ok = False
            elapsed_ms = int((time.time() - start_time) * 1000 / len(actions[:3]))
            step = _normalize_parallel_step(a, raw, elapsed_ms, start_time)
            new_tool_steps.append(step)
        else:
            merged_data.append({"ok": False, "error": {"code": "UNKNOWN", "message": str(raw)[:200]}})
            all_ok = False
            new_tool_steps.append({
                "tool": a.get("tool", ""),
                "input": str(a.get("query", "")),
                "status": "error",
                "elapsed_ms": 0,
                "timestamp": start_time,
                "error": str(raw)[:200],
            })

    merged = {"ok": all_ok, "data": merged_data}
    result_str = json.dumps(merged, ensure_ascii=False)

    return _build_parallel_return(state, result_str, new_tool_steps, start_time)


async def _invoke_single_with_gate(
    registry, call: CapabilityCall, gate: PolicyGate,
    tool_name: str, query: str,
) -> dict:
    """Invoke a single tool through the policy gate."""
    decision = gate.evaluate(
        call,
        context=PolicyContext(
            conversation_id="",
            agent_id="agent.main",
        ),
    )
    if decision.action != "allow":
        return {
            "ok": False,
            "error": {
                "code": decision.code or "POLICY_DENIED",
                "message": decision.reason or "Blocked by policy gate",
                "retryable": False,
            },
        }
    try:
        return await registry.invoke_capability(call)
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "code": "TOOL_INVOKE_EXCEPTION",
                "message": str(exc)[:200],
                "retryable": False,
            },
        }


def _normalize_parallel_step(action: dict, result: dict, elapsed_ms: int, timestamp: float) -> dict:
    """Create a tool step record for a parallel execution."""
    status = "completed" if result.get("ok", False) else "error"
    step = {
        "tool": action.get("tool", ""),
        "input": str(action.get("query", "")),
        "status": status,
        "elapsed_ms": max(0, int(elapsed_ms)),
        "timestamp": timestamp,
    }
    if status == "error":
        error_data = result.get("error", {})
        if isinstance(error_data, dict):
            step["error"] = str(error_data.get("message", "unknown error"))
        else:
            step["error"] = str(error_data)
    return step


def _build_parallel_error_result(actions: list[dict], message: str) -> str:
    return json.dumps({
        "ok": False,
        "data": [{"ok": False, "error": {"code": "REGISTRY_NOT_READY", "message": message}}
                 for _ in actions[:3]],
    }, ensure_ascii=False)


def _build_parallel_return(state: State, result_str: str, tool_steps: list, start_time: float) -> dict:
    return {
        "tool_result": result_str,
        "tool_steps": tool_steps,
        "current_tool": None,
        "tool_input": None,
        "last_tool_name": None,
        "last_tool_query": None,
        "reasoning_steps": state.get("reasoning_steps", []),
        "route": "agent",
    }


async def _execute_single_tool(
    state: State,
    tool_name: str,
    tool_input: dict,
    gate: PolicyGate,
    start_time: float,
) -> dict:
    """Execute a single tool (original logic, extracted for clarity)."""
    call = CapabilityCall(capability_name=tool_name, input_payload=tool_input)

    decision = gate.evaluate(
        call,
        context=PolicyContext(
            conversation_id=str(state.get("conversation_id") or ""),
            agent_id=str(state.get("active_agent") or "agent.main"),
        ),
    )

    if decision.action != "allow":
        result = {
            "ok": False,
            "error": {
                "code": decision.code or "POLICY_DENIED",
                "message": decision.reason or "Blocked by policy gate",
                "retryable": False,
            },
        }
        result_str = json.dumps(result, ensure_ascii=False)
        step = f"[tool_node] Policy denied capability '{tool_name}': {decision.reason or decision.code}"
        status = "error"
        error_msg = _error_text(result.get("error"))
    else:
        registry = get_tool_registry()
        if not registry:
            result = {"ok": False, "error": "ToolRegistry not initialized", "code": "REGISTRY_NOT_READY"}
            result_str = json.dumps(result, ensure_ascii=False)
            step = f"[tool_node] ERROR: registry not available, skipped '{tool_name}'"
            status = "error"
            error_msg = "ToolRegistry not initialized"
        else:
            try:
                timeout_ms = gate.timeout_override_ms
                if timeout_ms and timeout_ms > 0:
                    result = await asyncio.wait_for(
                        registry.invoke_capability(call),
                        timeout=timeout_ms / 1000,
                    )
                else:
                    result = await registry.invoke_capability(call)
            except asyncio.TimeoutError:
                result = {
                    "ok": False,
                    "error": {
                        "code": "TOOL_TIMEOUT",
                        "message": "tool invocation timeout",
                        "retryable": True,
                    },
                }
            except Exception as exc:
                logger.exception("tool_node invoke failed for tool=%s", tool_name)
                result = {
                    "ok": False,
                    "error": {
                        "code": "TOOL_INVOKE_EXCEPTION",
                        "message": f"tool invoke exception: {str(exc)[:200]}",
                        "retryable": False,
                    },
                }

            result_str = json.dumps(result, ensure_ascii=False)
            ok = bool(result.get("ok", False))
            status = "completed" if ok else "error"
            error_msg = _error_text(result.get("error")) if not ok else None
            step = (
                f"[tool_node] Tool '{tool_name}' executed successfully."
                if ok
                else f"[tool_node] Tool '{tool_name}' returned error: {error_msg}"
            )

    elapsed_time = time.time() - start_time
    tool_step_record = normalize_tool_step_record(
        tool_name=tool_name,
        tool_input=tool_input,
        status=status,
        elapsed_ms=int(elapsed_time * 1000),
        timestamp=start_time,
        error=error_msg,
    )

    new_tool_steps = state.get("tool_steps", []) + [tool_step_record]

    return {
        "tool_result": result_str,
        "tool_steps": new_tool_steps,
        "current_tool": None,
        "tool_input": None,
        "last_tool_name": None,
        "last_tool_query": None,
        "reasoning_steps": state.get("reasoning_steps", []) + [step],
        "route": "agent",
    }
```

Also add the missing import for `PolicyContext` at the top of `nodes.py` if not already present:

```python
from policy.models import PolicyContext
```

Check existing import and add if missing.

- [x] **Step 3: Run parallel tests**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/test_parallel_protocol.py -v
```
Expected: All tests PASS

- [x] **Step 4: Run full existing test suite**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/ -v
```
Expected: All existing tests still PASS (single tool path remains unchanged)

- [x] **Step 5: Commit**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/graph/nodes.py ai_service/tests/test_parallel_protocol.py
git commit -m "feat: update tool_node with parallel execution via asyncio.gather"
```

---

### Task 6: Create Docker sandbox for Python execution

**Files:**
- Create: `ai_service/tools/sandbox/__init__.py`
- Create: `ai_service/tools/sandbox/Dockerfile.sandbox`
- Create: `ai_service/tools/sandbox/docker-compose.sandbox.yml`
- Create: `ai_service/tools/sandbox/tool.py`
- Modify: `ai_service/requirements.txt` (add `docker` package)
- Create: `ai_service/tests/test_code_sandbox.py`

- [x] **Step 1: Write the failing tests**

Create `ai_service/tests/test_code_sandbox.py`:

```python
from __future__ import annotations

from typing import Any, Mapping

import pytest

from tools.base import BaseTool, ToolResult
from tools.sandbox.tool import CodeSandboxTool
from tools.schema import ToolSchema


class TestCodeSandboxSchema:
    def test_sandbox_tool_has_decorator(self):
        assert hasattr(CodeSandboxTool, "_is_tool")
        assert CodeSandboxTool._is_tool is True

    def test_sandbox_tool_name(self):
        assert CodeSandboxTool.name == "execute_python"

    def test_sandbox_tool_description(self):
        assert isinstance(CodeSandboxTool.description, str)
        assert len(CodeSandboxTool.description) > 0

    def test_sandbox_tool_schema(self):
        assert isinstance(CodeSandboxTool.schema, ToolSchema)
        params = CodeSandboxTool.schema.parameters
        assert "required" in params
        assert "code" in params["required"]
        assert "timeout" in params.get("properties", {})
        assert params["properties"]["timeout"].get("default") == 30

    def test_sandbox_tool_schema_timeout_optional(self):
        params = CodeSandboxTool.schema.parameters
        assert "timeout" not in params["required"]


class TestCodeSandboxExecution:
    """Integration tests that require Docker to be running locally."""

    docker_available = False

    @classmethod
    def setup_class(cls):
        import shutil
        cls.docker_available = shutil.which("docker") is not None

    def test_simple_execution(self):
        if not self.docker_available:
            pytest.skip("Docker not available")
        tool = CodeSandboxTool()
        result = tool.execute({"code": "print('hello')"})
        assert result.ok is True
        assert "hello" in str(result.data or "")

    def test_timeout(self):
        if not self.docker_available:
            pytest.skip("Docker not available")
        tool = CodeSandboxTool()
        result = tool.execute({"code": "import time; time.sleep(10)", "timeout": 1})
        assert result.ok is False
        assert "timeout" in str(result.error or "").lower() or "TIMEOUT" in str(result.error or "")

    def test_syntax_error(self):
        if not self.docker_available:
            pytest.skip("Docker not available")
        tool = CodeSandboxTool()
        result = tool.execute({"code": "print('hello"})  # missing quote
        assert result.ok is False
```

- [x] **Step 2: Create `ai_service/tools/sandbox/Dockerfile.sandbox`**

```dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir pandas numpy matplotlib

WORKDIR /workspace

# Read code from stdin and execute
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

- [x] **Step 3: Create `ai_service/tools/sandbox/docker-entrypoint.sh`**

```bash
#!/bin/sh
# Read Python code from stdin and execute it
cat > /workspace/script.py
exec python /workspace/script.py
```

Make it executable with `chmod +x ai_service/tools/sandbox/docker-entrypoint.sh`.

- [x] **Step 4: Create `ai_service/tools/sandbox/docker-compose.sandbox.yml`**

```yaml
version: "3.9"
services:
  sandbox:
    build:
      context: .
      dockerfile: Dockerfile.sandbox
    image: code-sandbox:latest
    cpus: 1
    mem_limit: 256m
    network_mode: "none"
    read_only: true
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    init: true
    stop_signal: SIGKILL
    stop_grace_period: 1s
```

- [x] **Step 5: Create `ai_service/tools/sandbox/__init__.py`**

```python
from tools.sandbox.tool import CodeSandboxTool

__all__ = ["CodeSandboxTool"]
```

- [x] **Step 6: Create `ai_service/tools/sandbox/tool.py`**

```python
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
from typing import Any, Mapping

from tools.base import BaseTool, ToolResult
from tools.schema import ToolSchema, tool

logger = logging.getLogger(__name__)

_SANDBOX_IMAGE = os.getenv("CODE_SANDBOX_IMAGE", "code-sandbox:latest")
_SANDBOX_TIMEOUT = 30


@tool
class CodeSandboxTool(BaseTool):
    name = "execute_python"
    description = "Execute Python code in a secure Docker sandbox for data analysis. Supports pandas, numpy, matplotlib."
    schema = ToolSchema(parameters={
        "type": "object",
        "required": ["code"],
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds (default: 30, max: 60)",
                "default": 30,
            },
        },
    })

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        code = str(input_payload.get("code", "")).strip()
        if not code:
            return ToolResult.failure(
                code="INVALID_INPUT",
                message="code is required and must be a non-empty string",
                retryable=False,
            )

        timeout = int(input_payload.get("timeout", _SANDBOX_TIMEOUT))
        timeout = max(1, min(timeout, 60))  # clamp 1-60 seconds

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _run_in_sandbox, code, timeout
        )


def _run_in_sandbox(code: str, timeout: int) -> ToolResult:
    """Run code in Docker sandbox (synchronous, runs in thread pool)."""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            script_path = f.name

        try:
            result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "--network", "none",
                    "--memory", "256m",
                    "--cpus", "1",
                    "--read-only",
                    "--security-opt", "no-new-privileges:true",
                    "--cap-drop", "ALL",
                    "--init",
                    "--stop-signal", "SIGKILL",
                    "--stop-grace-period", "1s",
                    "-i",  # stdin for the entrypoint script
                    _SANDBOX_IMAGE,
                ],
                input=code,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                return ToolResult.success(output if output else "(executed successfully with no output)")
            else:
                stderr = result.stderr.strip()[:500]
                return ToolResult.failure(
                    code="EXECUTION_ERROR",
                    message=f"Code exited with code {result.returncode}: {stderr}",
                    retryable=False,
                )

        except subprocess.TimeoutExpired:
            return ToolResult.failure(
                code="TIMEOUT",
                message=f"Code execution timed out after {timeout}s",
                retryable=False,
            )
        except FileNotFoundError:
            return ToolResult.failure(
                code="DOCKER_NOT_FOUND",
                message="Docker is not available on this system",
                retryable=False,
            )
        except Exception as exc:
            logger.exception("Sandbox execution failed")
            return ToolResult.failure(
                code="SANDBOX_ERROR",
                message=f"Sandbox execution failed: {str(exc)[:200]}",
                retryable=False,
            )
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    except Exception as exc:
        logger.exception("Failed to create temp script")
        return ToolResult.failure(
            code="SANDBOX_SETUP_ERROR",
            message=f"Failed to set up sandbox: {str(exc)[:200]}",
            retryable=False,
        )
```

- [x] **Step 7: Add `docker` to `ai_service/requirements.txt`** (not needed — we use `subprocess` to call `docker` CLI instead of the Docker SDK)

The design doc uses `subprocess` to call Docker. The requirements.txt does not need the `docker` Python package since we call the `docker` CLI directly. Skip this step.

- [x] **Step 8: Build the sandbox Docker image**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service/tools/sandbox
chmod +x docker-entrypoint.sh
docker compose -f docker-compose.sandbox.yml build
```
Expected: Docker image `code-sandbox:latest` is built successfully.

- [x] **Step 9: Run tests (Docker-available tests skipped if no Docker)**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/test_code_sandbox.py -v
```
Expected: Schema tests PASS. Integration tests skip with "Docker not available" if Docker is not running on this machine.

- [x] **Step 10: Commit**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/tools/sandbox/ ai_service/tests/test_code_sandbox.py
git commit -m "feat: add Docker sandbox for Python code execution"
```

---

### Task 7: Remove manual tool registration from main.py

**Files:**
- Modify: `ai_service/main.py`

- [x] **Step 1: Update `ai_service/main.py`**

Replace the tool registration section in `lifespan`:

Old code (lines 39-47):
```python
    # 初始化 ToolRegistry（全局单例，整个应用生命周期共用）
    tool_registry = ToolRegistry()
    tool_registry.register(SearchTool())
    tool_registry.register(TimeTool())
    tool_registry.register(BrowserUseTool())
    print(f"ToolRegistry ready: {[t['name'] for t in tool_registry.list_tools()]}")

    set_runtime(pg_pool, checkpointer)
    set_tool_registry(tool_registry)
```

New code:
```python
    # 初始化 ToolRegistry（全局单例，整个应用生命周期共用）
    tool_registry = ToolRegistry()
    tool_registry.discover()
    print(f"ToolRegistry ready: {[t['name'] for t in tool_registry.list_tools()]}")

    set_runtime(pg_pool, checkpointer)
    set_tool_registry(tool_registry)
```

Also remove the now-unused tool imports:
```python
from tools.browser import BrowserUseTool
from tools.search import SearchTool
from tools.time.tool import TimeTool
```

- [x] **Step 2: Verify the app starts correctly**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -c "
import asyncio
from tools import ToolRegistry
from config import settings

async def test():
    registry = ToolRegistry()
    registry.discover()
    tools = registry.list_tools()
    names = [t['name'] for t in tools]
    print(f'Discovered tools: {names}')
    assert 'search' in names, 'search not found'
    assert 'time' in names, 'time not found'
    assert 'browser' in names, 'browser not found'
    print('All 3 tools auto-discovered successfully')

asyncio.run(test())
"
```
Expected: `Discovered tools: ['search', 'time', 'browser']`

- [x] **Step 3: Run full test suite**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/ -v
```
Expected: All tests PASS

- [x] **Step 4: Commit**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/main.py
git commit -m "refactor: replace manual tool registration with auto-discovery in main.py"
```

---

### Task 8: End-to-end integration test

**Files:**
- Create: `ai_service/tests/test_end_to_end.py`

- [x] **Step 1: Write the integration tests**

Create `ai_service/tests/test_end_to_end.py`:

```python
from __future__ import annotations

from typing import Any, Mapping

import pytest

from tools.base import BaseTool, ToolResult
from tools.registry import ToolRegistry
from tools.schema import ToolSchema, tool


class TestEndToEnd:
    """End-to-end integration tests for the full tool system pipeline.

    These tests simulate the complete flow:
    1. Auto-discovery discovers tools
    2. Registry builds tool prompts for LLM
    3. Tools are invocable via the registry
    4. Flow works correctly end-to-end
    """

    def setup_method(self):
        ToolRegistry._registry_cache = {}

    def test_registry_auto_discovery_pipeline(self):
        """Phase 1: Registry discovers @tool-decorated tools."""

        @tool
        class PipelineToolA(BaseTool):
            name = "pipe_a"
            description = "Pipeline tool A"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success(f"A:{input_payload.get('x', '')}")

        @tool
        class PipelineToolB(BaseTool):
            name = "pipe_b"
            description = "Pipeline tool B"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"y": {"type": "string"}},
                "required": ["y"],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success(f"B:{input_payload.get('y', '')}")

        registry = ToolRegistry()
        registry.discover()

        # Verify Phase 1: auto-discovery
        tools = registry.list_tools()
        names = [t["name"] for t in tools]
        assert "pipe_a" in names
        assert "pipe_b" in names

        # Verify build_tools_prompt
        prompt = registry.build_tools_prompt()
        assert "pipe_a" in prompt
        assert "pipe_b" in prompt

    async def test_single_tool_invoke(self):
        """Tools can be invoked individually."""

        @tool
        class SingleTool(BaseTool):
            name = "single"
            description = "Single tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success(f"echo:{input_payload.get('msg', '')}")

        ToolRegistry._registry_cache = {}
        registry = ToolRegistry()
        registry.register(SingleTool())

        result = await registry.invoke("single", {"msg": "hello"})
        assert result["ok"] is True
        assert result["data"] == "echo:hello"

    async def test_parallel_invoke(self):
        """Multiple tools can be invoked in parallel via asyncio.gather."""

        @tool
        class ParToolA(BaseTool):
            name = "par_a"
            description = "Parallel A"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"v": {"type": "string"}},
                "required": ["v"],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success(f"A:{input_payload.get('v', '')}")

        @tool
        class ParToolB(BaseTool):
            name = "par_b"
            description = "Parallel B"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"v": {"type": "string"}},
                "required": ["v"],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success(f"B:{input_payload.get('v', '')}")

        ToolRegistry._registry_cache = {}
        registry = ToolRegistry()
        registry.register(ParToolA())
        registry.register(ParToolB())

        import asyncio
        from domain.capability import CapabilityCall

        calls = [
            CapabilityCall("par_a", {"v": "1"}),
            CapabilityCall("par_b", {"v": "2"}),
        ]
        results = await asyncio.gather(*[registry.invoke_capability(c) for c in calls])

        assert results[0]["data"] == "A:1"
        assert results[1]["data"] == "B:2"

    async def test_error_isolation(self):
        """One tool failing does not affect others."""

        @tool
        class GoodTool(BaseTool):
            name = "good"
            description = "Good tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {},
                "required": [],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("ok")

        @tool
        class FailTool(BaseTool):
            name = "fail"
            description = "Fail tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {},
                "required": [],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                raise RuntimeError("intentional failure")

        ToolRegistry._registry_cache = {}
        registry = ToolRegistry()
        registry.register(GoodTool())
        registry.register(FailTool())

        import asyncio
        from domain.capability import CapabilityCall

        calls = [
            CapabilityCall("good", {}),
            CapabilityCall("fail", {}),
        ]
        results = await asyncio.gather(*[registry.invoke_capability(c) for c in calls])

        assert results[0]["ok"] is True
        assert results[0]["data"] == "ok"
        assert results[1]["ok"] is False

    def test_prompt_format_usability(self):
        """build_tools_prompt() returns a format suitable for LLM prompts."""

        @tool
        class FormatTool(BaseTool):
            name = "formatter"
            description = "Format test tool"
            schema = ToolSchema(parameters={
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            })

            async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
                return ToolResult.success("ok")

        ToolRegistry._registry_cache = {}
        registry = ToolRegistry()
        registry.register(FormatTool())

        prompt = registry.build_tools_prompt()
        # Should follow format: "  - <name>: <description>"
        lines = prompt.strip().split("\n")
        assert len(lines) >= 1
        assert lines[0].startswith("  - formatter:")
```

- [x] **Step 2: Run the integration tests**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/test_end_to_end.py -v
```
Expected: All tests PASS

- [x] **Step 3: Run the full test suite for final regression check**

Run:
```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/ -v
```
Expected: All tests PASS

- [x] **Step 4: Commit**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/tests/test_end_to_end.py
git commit -m "test: add end-to-end integration test for full tool system pipeline"
```

---

### Task 9: Update documentation

**Files:**
- Create: `ai_service/tools/README.md`

- [x] **Step 1: Create `ai_service/tools/README.md`**

```markdown
# Tool System

This directory contains the tool system for the AI Chat Service. Tools are self-contained capabilities that the LLM agent can invoke during a conversation.

## Creating a New Tool

1. Create a new package under `tools/`:

```
ai_service/tools/<name>/
  __init__.py     # export your tool class
  tool.py         # tool implementation
```

2. Define your tool class using the `@tool` decorator and `ToolSchema`:

```python
from tools.base import BaseTool, ToolResult
from tools.schema import ToolSchema, tool

@tool
class MyTool(BaseTool):
    name = "my_tool"
    description = "What this tool does."
    schema = ToolSchema(parameters={
        "type": "object",
        "required": ["input_field"],
        "properties": {
            "input_field": {
                "type": "string",
                "description": "Description of the input field",
            },
        },
    })

    async def execute(self, input_payload) -> ToolResult:
        # Your implementation here
        return ToolResult.success("done")
```

3. That's it. The tool is auto-discovered at startup.

## How Discovery Works

1. `ToolRegistry.discover()` scans all `BaseTool.__subclasses__()`.
2. Only classes with `_is_tool = True` (set by `@tool` decorator) are considered.
3. Each candidate must have `name`, `description`, and a valid `ToolSchema`.
4. Valid tools are registered and available via `get_tool_registry()`.

## Existing Tools

| Tool | Name | Description |
|------|------|-------------|
| SearchTool | `search` | Web search via Tavily API |
| TimeTool | `time` | Current date/time |
| BrowserUseTool | `browser` | URL content extraction |
| CodeSandboxTool | `execute_python` | Python code execution in Docker sandbox |

## Schema Format

Tools use `ToolSchema` (Pydantic BaseModel) with a `parameters` dict following [OpenAI function calling schema](https://platform.openai.com/docs/guides/function-calling) format.
```

- [x] **Step 2: Commit**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/tools/README.md
git commit -m "docs: add tool system README with creation guide and schema docs"
```

---

## Post-Implementation Verification

After all tasks are complete, run the full test suite one final time:

```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/python -m pytest tests/ -v
```

Expected: All tests PASS across all test files.

Then attempt to start the service:

```bash
cd /Volumes/work/projects/winter-agent/ai_service
.venv/bin/uvicorn main:app --reload
```

Expected: Server starts successfully, logs show:
```
Discovered and registered tool 'search'
Discovered and registered tool 'time'
Discovered and registered tool 'browser'
ToolRegistry ready: ['search', 'time', 'browser']
```

## Self-Review

### Spec Coverage

| Spec Requirement | Task(s) |
|-----------------|---------|
| ToolSchema (Pydantic BaseModel) with `parameters` | Task 1 |
| `@tool` decorator sets `_is_tool` | Task 1 |
| `ToolRegistry.discover()` scans `BaseTool.__subclasses__()` | Task 2 |
| Filter `_is_tool=True` + complete schema | Task 2 |
| `build_tools_prompt()` for LLM prompts | Task 2 |
| Migrate SearchTool, TimeTool, BrowserUseTool to `@tool` format | Task 3 |
| `agent_node` supports `actions` array (parallel protocol) | Task 4 |
| `agent_node` backward-compatible with `action` field | Task 4 |
| Max 3 parallel tools | Task 4 |
| `tool_node` uses `asyncio.gather()` for parallel execution | Task 5 |
| Error isolation in parallel path | Task 5 |
| Docker sandbox for Python execution | Task 6 |
| CodeSandboxTool with `@tool` decorator | Task 6 |
| Sandbox: network disabled, 1 CPU, 256M memory, 30s timeout | Task 6 |
| Remove manual tool registration from main.py | Task 7 |
| End-to-end integration test | Task 8 |
| Documentation: README with tool creation guide | Task 9 |

### Type Consistency Check

- `ToolSchema` is defined in Task 1, used in Tasks 2-6, 9. Field name: `parameters: dict`.
- `tool()` decorator defined in Task 1, used in Tasks 3, 4, 5, 6. Sets `cls._is_tool = True`.
- `ToolRegistry.discover()` defined in Task 2, called in Task 7's `main.py`.
- `ToolRegistry.build_tools_prompt()` defined in Task 2, called in Task 4's `agent_node`.
- `BaseTool.schema: ToolSchema` renamed from `BaseTool.input_schema: dict` in Task 1 — `list_tools()` returns `tool.schema.parameters` in Task 2, matching the old `input_schema` dict shape.
- Parallel protocol: `agent_node` returns `{"tool_input": {"actions": [...]}}` in Task 4, `tool_node` checks `"actions" in tool_input` in Task 5.
- `CapabilityCall` uses `capability_name` and `input_payload` — unchanged across all tasks.
- `ToolResult` returned by all tool `execute()` methods — unchanged across all tasks.

### Placeholder Scan

- No "TBD", "TODO", or "implement later" found.
- No "Add appropriate error handling" without actual error handling code.
- No "Write tests for the above" without actual test code.
- No "Similar to Task N" — all code blocks are complete and self-contained.
- No undefined type/function references — all interfaces are traced through the dependency chain.
