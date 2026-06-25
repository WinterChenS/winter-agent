from __future__ import annotations

from typing import Any, Mapping

import pytest

from tools.base import BaseTool, ToolResult
from tools.registry import ToolNotFoundError, ToolRegistry
from tools.schema import ToolSchema, tool


# ---------------------------------------------------------------------------
# Helper: concrete tool classes used across tests
# ---------------------------------------------------------------------------

@tool
class ValidTool(BaseTool):
    """A @tool-decorated tool with a valid schema."""

    name: str = "valid_tool"
    description: str = "A valid tool for testing"
    schema: ToolSchema = ToolSchema(
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    )

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data={"result": "ok"})


class UndecoratedTool(BaseTool):
    """A BaseTool subclass WITHOUT the @tool decorator."""

    name: str = "undecorated_tool"
    description: str = "Should not be auto-discovered"
    schema: ToolSchema = ToolSchema(
        parameters={
            "type": "object",
            "properties": {},
        },
    )

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data={})


@tool
class ToolWithoutSchema(BaseTool):
    """A @tool-decorated tool that has schema = None."""

    name: str = "no_schema_tool"
    description: str = "Has no schema"
    schema: ToolSchema | None = None

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data={})


@tool
class ToolWithParamDetails(BaseTool):
    """A @tool-decorated tool with detailed parameter info."""

    name: str = "param_tool"
    description: str = "Tool with parameters"
    schema: ToolSchema = ToolSchema(
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The user name"},
                "age": {"type": "integer", "description": "The user age"},
            },
            "required": ["name"],
        },
    )

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data={})


class TestDiscover:
    """Tests for ToolRegistry.discover()."""

    def test_discover_registers_tool_decorated_subclass(self):
        """discover() 应注册带有 @tool 装饰器的 BaseTool 子类。"""
        registry = ToolRegistry()
        registry.discover()
        tool = registry.get("valid_tool")
        assert tool is not None
        assert tool.name == "valid_tool"
        assert tool.description == "A valid tool for testing"

    def test_discover_skips_class_without_is_tool(self):
        """discover() 应跳过没有 _is_tool 的 BaseTool 子类。"""
        registry = ToolRegistry()
        registry.discover()
        with pytest.raises(ToolNotFoundError):
            registry.get("undecorated_tool")

    def test_discover_skips_class_without_schema(self):
        """discover() 应跳过 schema 为 None 的类。"""
        registry = ToolRegistry()
        registry.discover()
        with pytest.raises(ToolNotFoundError):
            registry.get("no_schema_tool")


class TestBuildToolsPrompt:
    """Tests for ToolRegistry.build_tools_prompt()."""

    def test_build_tools_prompt_contains_tool_name_and_description(self):
        """build_tools_prompt() 应返回包含工具名称和描述的字符串。"""
        registry = ToolRegistry()
        registry.register(ValidTool())
        prompt = registry.build_tools_prompt()
        assert "valid_tool" in prompt
        assert "A valid tool for testing" in prompt

    def test_build_tools_prompt_empty_registry(self):
        """build_tools_prompt() 在注册表为空时应返回空字符串或占位符。"""
        registry = ToolRegistry()
        prompt = registry.build_tools_prompt()
        assert prompt == "" or "no tools" in prompt.lower()

    def test_build_tools_prompt_includes_parameter_info(self):
        """build_tools_prompt() 应包含 schema 中的参数信息。"""
        registry = ToolRegistry()
        registry.register(ToolWithParamDetails())
        prompt = registry.build_tools_prompt()
        assert "param_tool" in prompt
        assert "Tool with parameters" in prompt
        assert "name" in prompt
        assert "age" in prompt
        assert "string" in prompt
        assert "integer" in prompt
