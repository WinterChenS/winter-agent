from __future__ import annotations

from dataclasses import dataclass, field

from domain.capability import CapabilityCall
from policy.models import PolicyContext, PolicyDecision


@dataclass(slots=True)
class PolicyGate:
	tool_whitelist: set[str] = field(default_factory=set)
	max_query_len: int = 500
	timeout_override_ms: int | None = None

	def evaluate(self, call: CapabilityCall, context: PolicyContext | None = None) -> PolicyDecision:
		_ = context

		capability = call.capability_name.strip()
		if self.tool_whitelist and capability not in self.tool_whitelist:
			return PolicyDecision(
				action="deny",
				code="POLICY_TOOL_NOT_ALLOWED",
				reason=f"Capability '{capability}' is not whitelisted",
			)

		payload = call.input_payload
		query = str(payload.get("query", "")) if isinstance(payload, dict) else ""
		if len(query) > self.max_query_len:
			return PolicyDecision(
				action="deny",
				code="POLICY_QUERY_TOO_LONG",
				reason=f"Query length exceeds max_query_len={self.max_query_len}",
			)

		return PolicyDecision(action="allow")

