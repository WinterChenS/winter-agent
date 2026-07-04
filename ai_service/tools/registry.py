from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Mapping

from domain.capability import CapabilityCall, CapabilityResult, CapabilitySpec
from tools.base import BaseTool, ToolResult
from tools.metrics import ToolMetrics

PreHook = Callable[[str, dict], Awaitable[dict | None]]  # Return modified input or None to reject
PostHook = Callable[[str, dict, dict], Awaitable[None]]   # (name, input, result)

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
		self._metrics: dict[str, ToolMetrics] = {}
		self._pre_hooks: list[PreHook] = []
		self._post_hooks: list[PostHook] = []

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

	@staticmethod
	def _walk_subclasses(cls: type) -> list[type]:
		"""Recursively collect all subclasses of *cls* (not just direct)."""
		result: list[type] = []
		for sub in cls.__subclasses__():
			result.append(sub)
			result.extend(ToolRegistry._walk_subclasses(sub))
		return result

	def discover(self) -> None:
		"""Auto-discover and register all @tool-decorated BaseTool subclasses.

		Recursively scans the ``BaseTool`` subclass tree for classes that have
		``_is_tool = True`` (set by the ``@tool`` decorator) and a non-``None``
		``schema``.  Each valid class is instantiated and registered via
		``register()``.

		Incomplete tools (missing ``_is_tool`` or missing schema) are skipped
		with a warning logged.
		"""
		for cls in self._walk_subclasses(BaseTool):
			if not getattr(cls, "_is_tool", False):
				logger.warning("Skipping %s: missing _is_tool marker", cls.__name__)
				continue
			if cls.schema is None:
				logger.warning("Skipping %s: schema is None", cls.__name__)
				continue
			if not isinstance(cls.schema.parameters, dict) or not cls.schema.parameters:
				logger.warning("Skipping %s: schema.parameters is empty or not a dict", cls.__name__)
				continue
			if "properties" not in cls.schema.parameters:
				logger.warning("Skipping %s: schema.parameters missing 'properties' key", cls.__name__)
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


	def record_metric(self, name: str, elapsed_ms: int, status: str) -> None:
		"""Record a tool invocation metric."""
		if name not in self._metrics:
			self._metrics[name] = ToolMetrics()
		m = self._metrics[name]
		m.invoke_count += 1
		m.total_latency_ms += elapsed_ms
		if status != "completed":
			m.error_count += 1

	def get_metrics(self, name: str) -> ToolMetrics | None:
		"""Return metrics for a tool, or None if never invoked."""
		return self._metrics.get(name)

	def register_pre_hook(self, hook: PreHook) -> None:
		"""Register a pre-execution hook."""
		self._pre_hooks.append(hook)

	def register_post_hook(self, hook: PostHook) -> None:
		"""Register a post-execution hook."""
		self._post_hooks.append(hook)

	async def _run_pre_hooks(self, name: str, input_payload: dict) -> dict | None:
		"""Run all pre-hooks in order. Returns modified input or None to reject."""
		current_input = input_payload
		for hook in self._pre_hooks:
			result = await hook(name, current_input)
			if result is None:
				return None  # rejected
			current_input = result
		return current_input

	async def _run_post_hooks(self, name: str, input_payload: dict, result: dict) -> None:
		"""Run all post-hooks in order."""
		for hook in self._post_hooks:
			await hook(name, input_payload, result)

	async def invoke(self, name: str, input_payload: Mapping[str, Any]) -> dict[str, Any]:
		# Run pre-hooks
		prepped = await self._run_pre_hooks(name, dict(input_payload))
		if prepped is None:
			return {"ok": False, "error": {"code": "HOOK_REJECTED", "message": "Tool invocation rejected by pre-hook", "retryable": False}}
		tool = self.get(name)
		result = await tool.execute(prepped)
		if isinstance(result, ToolResult):
			result_dict = result.to_dict()
		else:
			result_dict = dict(result) if isinstance(result, Mapping) else None
		if result_dict is None:
			raise ToolRegistryError(
				f"Tool '{name}' returned an unsupported result type: {type(result).__name__}"
			)
		# Run post-hooks
		await self._run_post_hooks(name, prepped, result_dict)
		return result_dict

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
