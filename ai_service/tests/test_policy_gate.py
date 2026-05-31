from domain.capability import CapabilityCall
from policy.gate import PolicyGate


def test_deny_non_whitelisted_tool():
    gate = PolicyGate(tool_whitelist={"search"}, max_query_len=100)
    decision = gate.evaluate(CapabilityCall(capability_name="time", input_payload={"query": "now"}))

    assert decision.action == "deny"
    assert decision.code == "POLICY_TOOL_NOT_ALLOWED"


def test_deny_oversized_query():
    gate = PolicyGate(tool_whitelist=set(), max_query_len=5)
    decision = gate.evaluate(CapabilityCall(capability_name="search", input_payload={"query": "123456"}))

    assert decision.action == "deny"
    assert decision.code == "POLICY_QUERY_TOO_LONG"


def test_allow_default_tools():
    gate = PolicyGate(tool_whitelist={"search", "time"}, max_query_len=50)
    decision = gate.evaluate(CapabilityCall(capability_name="search", input_payload={"query": "hangzhou"}))

    assert decision.action == "allow"

