from __future__ import annotations

from typing import Any, Mapping

import pytest

from tools.base import BaseTool, ToolResult
from tools.schema import ToolSchema
from tools.schema_adapter import ToolSchemaAdapter


class _EchoTool(BaseTool):
    name: str = "echo"
    description: str = "Echoes input back"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Message to echo"},
        },
        "required": ["message"],
    }
    schema: ToolSchema = ToolSchema(
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to echo"},
            },
            "required": ["message"],
        },
    )

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data=input_payload)


class TestToolSchemaAdapter:
    def test_to_openai_format(self):
        """to_openai() 应输出 OpenAI function-calling 格式。"""
        tool = _EchoTool()
        result = ToolSchemaAdapter.to_openai(tool)
        assert result["type"] == "function"
        assert result["function"]["name"] == "echo"
        assert "description" in result["function"]
        assert "parameters" in result["function"]
        assert result["function"]["parameters"]["properties"]["message"]["type"] == "string"

    def test_to_anthropic_format(self):
        """to_anthropic() 应输出 Anthropic tool use 格式。"""
        tool = _EchoTool()
        result = ToolSchemaAdapter.to_anthropic(tool)
        assert result["name"] == "echo"
        assert "description" in result
        assert "input_schema" in result
        assert result["input_schema"]["properties"]["message"]["type"] == "string"

    def test_to_openai_includes_all_tools_in_registry(self):
        """遍历 registry 中所有工具时每个都应生成合法格式。"""
        from tools.registry import ToolRegistry
        registry = ToolRegistry()
        registry.register(_EchoTool())
        for t in registry.list_tools():
            tool = registry.get(t["name"])
            oai = ToolSchemaAdapter.to_openai(tool)
            assert "function" in oai
            assert oai["function"]["name"] == t["name"]

    def test_to_anthropic_includes_description(self):
        """Anthropic 格式必须包含 description 字段。"""
        tool = _EchoTool()
        result = ToolSchemaAdapter.to_anthropic(tool)
        assert result["description"] == "Echoes input back"
