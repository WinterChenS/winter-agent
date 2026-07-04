from __future__ import annotations

from typing import Any

from tools.base import BaseTool


class ToolSchemaAdapter:
    """Converts tool definitions between LLM provider schema formats.

    Usage::
        oai_schema = ToolSchemaAdapter.to_openai(my_tool)
        anth_schema = ToolSchemaAdapter.to_anthropic(my_tool)
    """

    @staticmethod
    def to_openai(tool: BaseTool) -> dict[str, Any]:
        """Convert BaseTool to OpenAI function-calling format.

        Returns:
            dict with ``type`` and ``function`` keys per OpenAI spec.
        """
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": _extract_parameters(tool),
            },
        }

    @staticmethod
    def to_anthropic(tool: BaseTool) -> dict[str, Any]:
        """Convert BaseTool to Anthropic tool-use format.

        Returns:
            dict with ``name``, ``description``, and ``input_schema`` keys.
        """
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": _extract_parameters(tool),
        }


def _extract_parameters(tool: BaseTool) -> dict[str, Any]:
    """Extract the JSON Schema parameters dict from a tool.

    Priority: ``tool.schema.parameters`` -> ``tool.input_schema`` -> fallback ``{}``.
    """
    if tool.schema is not None and tool.schema.parameters:
        return tool.schema.parameters
    if tool.input_schema:
        # input_schema is the full JSON Schema (includes "type": "object")
        return tool.input_schema
    return {"type": "object", "properties": {}}
