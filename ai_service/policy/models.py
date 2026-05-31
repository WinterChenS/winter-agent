from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PolicyAction = Literal["allow", "deny", "redact", "sandbox_only"]


@dataclass(slots=True)
class PolicyDecision:
	action: PolicyAction
	reason: str = ""
	code: str | None = None


@dataclass(slots=True)
class PolicyContext:
	conversation_id: str = ""
	agent_id: str = "agent.main"

