from __future__ import annotations

from typing import Any, Mapping

from domain.capability import CapabilityCall, CapabilityResult, CapabilitySpec
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

	def list_capabilities(self) -> list[dict[str, Any]]:
		return [
			CapabilitySpec(
				name=tool.name,
				version=getattr(tool, "version", "1.0.0"),
				kind="tool",
				description=tool.description,
				input_schema=getattr(tool, "input_schema", {}),
				output_schema=getattr(tool, "output_schema", {}),
				timeout_ms=getattr(tool, "timeout_ms", 30000),
				retry_policy=getattr(tool, "retry_policy", {"max_retries": 0}),
				policy_tags=getattr(tool, "policy_tags", []),
			).to_dict()
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


