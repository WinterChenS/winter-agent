from __future__ import annotations

from typing import Any, Mapping

from tools.base import BaseTool, ToolResult


class ToolRegistryError(Exception):
	"""Base error for tool registry issues."""


class DuplicateToolError(ToolRegistryError):
	"""Raised when a tool name is already registered."""


class ToolNotFoundError(ToolRegistryError):
	"""Raised when a tool name does not exist."""


class ToolRegistry:
	def __init__(self) -> None:
		self._tools: dict[str, BaseTool] = {}

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
				"input_schema": tool.input_schema,
			}
			for tool in self._tools.values()
		]

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


