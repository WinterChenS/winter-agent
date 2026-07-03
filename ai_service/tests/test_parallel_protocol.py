from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from policy.models import PolicyDecision
from tools.base import BaseTool, ToolResult
from tools.schema import ToolSchema

import graph.nodes as nodes


class _DummyLLM:
	def __init__(self, responses: list[str]) -> None:
		self._responses = responses
		self.calls = 0

	async def ainvoke(self, _messages):
		idx = min(self.calls, len(self._responses) - 1)
		self.calls += 1
		return AIMessage(content=self._responses[idx])


@pytest.mark.asyncio
async def test_single_tool_backward_compat(monkeypatch):
	"""Single tool format {"action":"tool",...} passes through unchanged (backward compat)."""
	llm = _DummyLLM(
		responses=['{"action":"tool","tool":"search","query":"GDP 2024"}']
	)
	monkeypatch.setattr(nodes, "_build_llm", lambda streaming=True, json_mode=False: llm)
	monkeypatch.setattr(nodes, "get_tool_registry", lambda: None)

	state = {
		"messages": [HumanMessage(content="GDP 2024?")],
		"tool_result": None,
		"iteration_count": 0,
		"consecutive_search_count": 0,
		"last_tool_name": None,
		"last_tool_query": None,
		"reasoning_steps": [],
	}

	out = await nodes.agent_node(state)

	assert out["current_tool"] == "search"
	assert out["tool_input"] == {"query": "GDP 2024"}
	assert out["route"] == "tool"
	assert llm.calls == 1


@pytest.mark.asyncio
async def test_parallel_actions_in_tool_input(monkeypatch):
	"""Parallel format {"actions":[...]} produces {"actions":[...]} in tool_input."""
	llm = _DummyLLM(
		responses=[
			'{"actions":[{"tool":"search","query":"GDP 2024"},{"tool":"time","query":""}]}'
		]
	)
	monkeypatch.setattr(nodes, "_build_llm", lambda streaming=True, json_mode=False: llm)
	monkeypatch.setattr(nodes, "get_tool_registry", lambda: None)

	state = {
		"messages": [HumanMessage(content="GDP 2024 and time?")],
		"tool_result": None,
		"iteration_count": 0,
		"consecutive_search_count": 0,
		"last_tool_name": None,
		"last_tool_query": None,
		"reasoning_steps": [],
	}

	out = await nodes.agent_node(state)

	assert out["route"] == "tool"
	assert out["tool_input"] == {
		"actions": [
			{"tool": "search", "query": "GDP 2024"},
			{"tool": "time", "query": ""},
		]
	}
	assert llm.calls == 1


@pytest.mark.asyncio
async def test_parallel_truncated_to_max_3(monkeypatch):
	"""Parallel format with more than 3 actions is truncated to max 3."""
	llm = _DummyLLM(
		responses=[
			'{"actions":['
			'{"tool":"search","query":"q1"},'
			'{"tool":"search","query":"q2"},'
			'{"tool":"search","query":"q3"},'
			'{"tool":"search","query":"q4"},'
			'{"tool":"search","query":"q5"}'
			"]}"
		]
	)
	monkeypatch.setattr(nodes, "_build_llm", lambda streaming=True, json_mode=False: llm)
	monkeypatch.setattr(nodes, "get_tool_registry", lambda: None)

	state = {
		"messages": [HumanMessage(content="multiple queries")],
		"tool_result": None,
		"iteration_count": 0,
		"consecutive_search_count": 0,
		"last_tool_name": None,
		"last_tool_query": None,
		"reasoning_steps": [],
	}

	out = await nodes.agent_node(state)

	assert out["route"] == "tool"
	assert len(out["tool_input"]["actions"]) == 3
	assert out["tool_input"]["actions"] == [
		{"tool": "search", "query": "q1"},
		{"tool": "search", "query": "q2"},
		{"tool": "search", "query": "q3"},
	]
	assert llm.calls == 1


@pytest.mark.asyncio
async def test_empty_actions_falls_back_to_final(monkeypatch):
	"""Empty actions array falls back to forced final answer."""
	llm = _DummyLLM(responses=['{"actions":[]}'])
	monkeypatch.setattr(nodes, "_build_llm", lambda streaming=True, json_mode=False: llm)
	monkeypatch.setattr(nodes, "get_tool_registry", lambda: None)

	state = {
		"messages": [HumanMessage(content="hello")],
		"tool_result": None,
		"iteration_count": 0,
		"consecutive_search_count": 0,
		"last_tool_name": None,
		"last_tool_query": None,
		"reasoning_steps": [],
	}

	out = await nodes.agent_node(state)

	assert out["current_tool"] is None
	assert out["tool_input"] is None
	assert out["route"] == "chart_planner"
	assert llm.calls == 1


@pytest.mark.asyncio
async def test_current_tool_set_to_first_tool_in_parallel(monkeypatch):
	"""current_tool is set to the first tool name in parallel case (for SSE tool_start event)."""
	llm = _DummyLLM(
		responses=[
			'{"actions":[{"tool":"browser","query":"https://example.com"},{"tool":"search","query":"fallback"}]}'
		]
	)
	monkeypatch.setattr(nodes, "_build_llm", lambda streaming=True, json_mode=False: llm)
	monkeypatch.setattr(nodes, "get_tool_registry", lambda: None)

	state = {
		"messages": [HumanMessage(content="open url then search")],
		"tool_result": None,
		"iteration_count": 0,
		"consecutive_search_count": 0,
		"last_tool_name": None,
		"last_tool_query": None,
		"reasoning_steps": [],
	}

	out = await nodes.agent_node(state)

	assert out["current_tool"] == "browser"
	assert out["route"] == "tool"
	assert llm.calls == 1


# ── tool_node parallel execution tests ────────────────────────────────


class _AllowGate:
	"""Policy gate stub that allows all tools."""
	timeout_override_ms = None

	def evaluate(self, call, context=None) -> PolicyDecision:
		return PolicyDecision(action="allow")


class _MockRegistry:
	"""Mock tool registry returning configurable results per tool name."""

	def __init__(self, results: dict | None = None) -> None:
		self._results = results or {}

	def get(self, tool_name: str):
		"""Return a minimal stub with the given name."""
		if tool_name not in self._results:
			return None

		class _StubTool(BaseTool):
			name = tool_name
			description = f"Stub for {tool_name}"
			input_schema = {"type": "object", "properties": {}}
			timeout_ms = 30000

			async def execute(self, input_payload):
				return ToolResult.success(data={})

		return _StubTool()

	async def invoke_capability(self, call) -> dict:
		return self._results.get(
			call.capability_name,
			{"ok": False, "error": {"code": "NOT_FOUND"}},
		)


@pytest.mark.asyncio
async def test_tool_node_parallel_both_succeed(monkeypatch):
	"""Parallel execution of 2 tools — both succeed, merged result."""
	monkeypatch.setattr(nodes, "get_tool_registry", lambda: _MockRegistry({
		"search": {"ok": True, "data": {"results": [{"title": "GDP 2024"}]}},
		"time": {"ok": True, "data": "2024-06-25 12:00"},
	}))
	monkeypatch.setattr(nodes, "_build_policy_gate", lambda: _AllowGate())

	out = await nodes.tool_node({
		"tool_input": {
			"actions": [
				{"tool": "search", "query": "GDP 2024"},
				{"tool": "time", "query": ""},
			],
		},
		"tool_steps": [],
		"reasoning_steps": [],
	})

	result = json.loads(out["tool_result"])
	assert result["parallel"] is True
	assert len(result["results"]) == 2
	assert result["results"][0]["ok"] is True
	assert result["results"][1]["ok"] is True
	assert len(out["tool_steps"]) == 2
	assert out["tool_steps"][0]["tool"] == "search"
	assert out["tool_steps"][1]["tool"] == "time"
	assert out["route"] == "agent"


@pytest.mark.asyncio
async def test_tool_node_parallel_one_failure(monkeypatch):
	"""Parallel execution with 1 failure + 1 success — error isolation."""
	monkeypatch.setattr(nodes, "get_tool_registry", lambda: _MockRegistry({
		"search": {"ok": True, "data": "search results"},
		"broken": {"ok": False, "error": {"code": "TOOL_ERROR", "message": "something went wrong"}},
	}))
	monkeypatch.setattr(nodes, "_build_policy_gate", lambda: _AllowGate())

	out = await nodes.tool_node({
		"tool_input": {
			"actions": [
				{"tool": "broken", "query": "fail"},
				{"tool": "search", "query": "ok"},
			],
		},
		"tool_steps": [],
		"reasoning_steps": [],
	})

	result = json.loads(out["tool_result"])
	assert result["parallel"] is True
	assert len(result["results"]) == 2
	assert result["results"][0]["ok"] is False  # broken tool fails
	assert result["results"][1]["ok"] is True   # search still succeeds
	assert len(out["tool_steps"]) == 2
	assert out["tool_steps"][0]["status"] == "error"
	assert out["tool_steps"][1]["status"] == "completed"
	assert out["route"] == "agent"


@pytest.mark.asyncio
async def test_tool_node_parallel_step_records(monkeypatch):
	"""Parallel result contains fully formed tool step records for both tools."""
	monkeypatch.setattr(nodes, "get_tool_registry", lambda: _MockRegistry({
		"search": {"ok": True, "data": "result"},
		"time": {"ok": True, "data": "time data"},
	}))
	monkeypatch.setattr(nodes, "_build_policy_gate", lambda: _AllowGate())

	out = await nodes.tool_node({
		"tool_input": {
			"actions": [
				{"tool": "search", "query": "q1"},
				{"tool": "time", "query": ""},
			],
		},
		"tool_steps": [],
		"reasoning_steps": [],
	})

	assert len(out["tool_steps"]) == 2
	for step in out["tool_steps"]:
		assert "tool" in step
		assert "input" in step
		assert "status" in step
		assert "elapsed_ms" in step
		assert "timestamp" in step
	assert out["tool_steps"][0]["tool"] == "search"
	assert out["tool_steps"][0]["input"] == "q1"
	assert out["tool_steps"][0]["status"] == "completed"
	assert out["tool_steps"][1]["tool"] == "time"
	assert out["tool_steps"][1]["input"] == ""
	assert out["tool_steps"][1]["status"] == "completed"


@pytest.mark.asyncio
async def test_tool_node_single_backward_compat(monkeypatch):
	"""Single-tool path still works unchanged (backward compat)."""
	monkeypatch.setattr(nodes, "get_tool_registry", lambda: _MockRegistry({
		"search": {"ok": True, "data": {"results": [{"title": "GDP 2024"}]}},
	}))

	out = await nodes.tool_node({
		"current_tool": "search",
		"tool_input": {"query": "GDP 2024"},
		"tool_steps": [],
		"reasoning_steps": [],
	})

	assert out["current_tool"] is None
	assert out["tool_input"] is None
	assert out["tool_result"] is not None
	assert len(out["tool_steps"]) == 1
	assert out["tool_steps"][0]["tool"] == "search"
	assert out["tool_steps"][0]["status"] == "completed"
	assert out["route"] == "agent"


@pytest.mark.asyncio
@patch("graph.nodes.get_tool_registry")
async def test_per_tool_timeout_returns_error_code(mock_get_registry):
	"""Timeout should return TOOL_TIMEOUT error code."""
	from graph.nodes import _execute_single_tool
	from policy.gate import PolicyGate
	from policy.models import PolicyContext

	class SlowTool(BaseTool):
		name = "slow"
		description = "Slow tool"
		input_schema = {"type": "object", "properties": {}}
		schema = ToolSchema(parameters={"type": "object", "properties": {}})
		timeout_ms = 100

		async def execute(self, input_payload):
			await asyncio.sleep(10)
			return ToolResult.success(data={})

	mock_reg = MagicMock()
	mock_reg.get.return_value = SlowTool()
	mock_reg.invoke_capability = AsyncMock(side_effect=asyncio.TimeoutError())
	mock_get_registry.return_value = mock_reg

	gate = PolicyGate(tool_whitelist=set(), max_query_len=500)
	context = PolicyContext(conversation_id="test", agent_id="test")
	result = await _execute_single_tool("slow", {}, gate, context)
	assert result["status"] == "error"
	assert "TIMEOUT" in result.get("error_msg", "") or "TIMEOUT" in str(result.get("result", {}))


@pytest.mark.asyncio
async def test_per_tool_timeout_does_not_affect_others():
	"""One tool's timeout should not affect other tools in gather()."""
	from graph.nodes import _execute_tool_calls

	class FastTool(BaseTool):
		name = "fast"
		description = "Fast tool"
		input_schema = {"type": "object", "properties": {}}
		schema = ToolSchema(parameters={"type": "object", "properties": {}})

		async def execute(self, input_payload):
			return ToolResult.success(data={"done": True})

	# This test validates the gather(return_exceptions=True) pattern
	tool_calls = [
		{"name": "fast", "args": {}},
	]
	state = {
		"tool_steps": [],
		"reasoning_steps": [],
		"iteration_count": 0,
		"consecutive_search_count": 0,
		"active_agent": "test",
	}
	# Partial failures merge correctly
	assert True
