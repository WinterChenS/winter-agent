from __future__ import annotations

import logging
from typing import Any, Mapping

from domain.capability import CapabilityCall, CapabilityResult, CapabilitySpec
from tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


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

	def discover(self) -> None:
		"""Auto-discover and register all @tool-decorated BaseTool subclasses.

		Scans ``BaseTool.__subclasses__()`` for classes that have ``_is_tool = True``
		(set by the ``@tool`` decorator) and a non-``None`` ``schema``.  Each valid
		class is instantiated and registered via ``register()``.

		Incomplete tools (missing ``_is_tool`` or missing schema) are skipped
		with a warning logged.
		"""
		for cls in BaseTool.__subclasses__():
			if not getattr(cls, "_is_tool", False):
				logger.warning("Skipping %s: missing _is_tool marker", cls.__name__)
				continue
			if cls.schema is None:
				logger.warning("Skipping %s: schema is None", cls.__name__)
				continue
			try:
				instance = cls()
				self.register(instance)
				logger.info("Registered tool: %s (%s)", instance.name, cls.__name__)
			except Exception:
				logger.exception("Failed to register %s", cls.__name__)

	def build_tools_prompt(self) -> str:
		"""Return a formatted prompt string listing all registered tools.

		Each entry includes the tool's name, description, and parameter
		information from its schema.  Returns an empty string when no tools
		are registered.
		"""
		if not self._tools:
			return ""

		lines: list[str] = ["## Available Tools", ""]
		for tool in self._tools.values():
			lines.append(f"- **{tool.name}**: {tool.description}")
			if tool.schema and tool.schema.parameters:
				props = tool.schema.parameters.get("properties", {})
				required_params = tool.schema.parameters.get("required", [])
				if props:
					lines.append("  Parameters:")
					for param_name, param_info in props.items():
						param_type = param_info.get("type", "any")
						param_desc = param_info.get("description", "")
						req = "required" if param_name in required_params else "optional"
						lines.append(f"  - {param_name} ({param_type}, {req}): {param_desc}")
			lines.append("")

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


