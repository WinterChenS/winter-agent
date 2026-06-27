# Creating a New Tool

## Quick Start

1. Create directory: `tools/calculator/`
2. Create `tools/calculator/__init__.py`:
   ```python
   from tools.calculator.tool import CalculatorTool
   ```
3. Create `tools/calculator/tool.py`:
   ```python
   import logging
   from typing import Any, Mapping

   from tools.base import BaseTool, ToolResult
   from tools.schema import tool, ToolSchema

   logger = logging.getLogger(__name__)

   @tool
   class CalculatorTool(BaseTool):
       name = "calculator"
       description = "Evaluate a mathematical expression and return the result"
       input_schema = {
           "type": "object",
           "required": ["expression"],
           "properties": {
               "expression": {
                   "type": "string",
                   "description": "The mathematical expression to evaluate, e.g. '2 + 2 * 3'",
               },
           },
       }
       schema: ToolSchema = ToolSchema(
           parameters={
               "type": "object",
               "required": ["expression"],
               "properties": {
                   "expression": {
                       "type": "string",
                       "description": "The mathematical expression to evaluate",
                   },
               },
           },
       )

       async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
           expr = input_payload.get("expression", "")
           if not expr:
               return ToolResult.failure("INVALID_INPUT", "expression is required", retryable=False)
           try:
               result = eval(expr)  # caution: use a safe parser in production
               return ToolResult.success({"result": result, "expression": expr})
           except Exception as exc:
               return ToolResult.failure("EVAL_ERROR", str(exc), retryable=True)
   ```
4. Register in `main.py`:
   ```python
   import tools.calculator.tool as _
   ```
5. Restart — the tool is auto-discovered at startup!

## How It Works

- `@tool` decorator sets `_is_tool = True` on the class, marking it for discovery
- `ToolRegistry.discover()` scans `BaseTool.__subclasses__()` for classes with `_is_tool` and a non-`None` `schema`
- Each valid class is instantiated and registered by name
- `ToolRegistry.build_tools_prompt()` generates the LLM prompt from all registered schemas
- At invocation, `ToolRegistry.invoke()` calls `tool.execute(input_payload)` and returns the result

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Unique identifier for the tool (used by LLM to call it) |
| `description` | `str` | Explains to the LLM what the tool does and when to use it |
| `input_schema` | `dict` | JSON Schema describing the expected input format |
| `schema` | `ToolSchema` | `ToolSchema(parameters=...)` wrapping the same schema for discovery |

## ToolResult

```python
# Success
return ToolResult.success({"key": "value"})

# Failure
return ToolResult.failure("ERROR_CODE", "Human readable message", retryable=False)
```

## Testing

```python
import pytest
from tools.calculator.tool import CalculatorTool

@pytest.mark.asyncio
async def test_calculator_add():
    tool = CalculatorTool()
    result = await tool.execute({"expression": "1 + 2"})
    assert result.ok
    assert result.data["result"] == 3
```

Place tests in `tests/test_tool_<name>.py`.
