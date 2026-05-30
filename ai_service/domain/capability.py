from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

CapabilityKind = Literal["tool", "skill", "mcp"]


@dataclass(slots=True)
class CapabilitySpec:
    name: str
    version: str = "1.0.0"
    kind: CapabilityKind = "tool"
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    timeout_ms: int = 30000
    retry_policy: dict[str, Any] = field(default_factory=lambda: {"max_retries": 0})
    policy_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "kind": self.kind,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "timeout_ms": self.timeout_ms,
            "retry_policy": self.retry_policy,
            "policy_tags": self.policy_tags,
        }


@dataclass(slots=True)
class CapabilityCall:
    capability_name: str
    input_payload: Mapping[str, Any]


@dataclass(slots=True)
class CapabilityResult:
    ok: bool
    data: Any = None
    error: dict[str, Any] | None = None

    @classmethod
    def success(cls, data: Any) -> "CapabilityResult":
        return cls(ok=True, data=data, error=None)

    @classmethod
    def failure(cls, code: str, message: str, retryable: bool = False) -> "CapabilityResult":
        return cls(
            ok=False,
            data=None,
            error={"code": code, "message": message, "retryable": retryable},
        )

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "data": self.data, "error": self.error}

