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
	input_schema: dict[str, Any]
	output_schema: dict[str, Any] = {}
	version: str = "1.0.0"
	timeout_ms: int = 30000
	retry_policy: dict[str, Any] = {"max_retries": 0}
	policy_tags: list[str] = []
	schema: ToolSchema | None = None

	@abstractmethod
	async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
		"""Execute the tool with validated input payload."""


