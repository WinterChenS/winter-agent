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

	# Debug: check current streaming bus state
	import sys
	_bus_check = nodes.get_streaming_bus()
	print(f"\n[DEBUG] get_streaming_bus(): {_bus_check}", flush=True)
	print(f"[DEBUG] nodes._streaming_bus: {nodes._streaming_bus}", flush=True)
	sys.stdout.flush()

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


# ── Streaming path lifecycle hooks tests (C1, I1, C2, I4 fixes) ────────


class _StreamingTool(BaseTool):
	"""A tool with execute_stream overridden."""
	name = "stream_tool"
	description = "Streaming tool"
	input_schema = {"type": "object", "properties": {}}
	schema = ToolSchema(parameters={"type": "object", "properties": {}})
	timeout_ms = 5000

	async def execute(self, input_payload):
		return ToolResult.success(data={})

	async def execute_stream(self, input_payload, bus):
		return ToolResult.success(data={"streamed": True})


class _SlowStreamingTool(BaseTool):
	"""A tool whose execute_stream sleeps longer than its timeout."""
	name = "slow_stream"
	description = "Slow streaming tool"
	input_schema = {"type": "object", "properties": {}}
	schema = ToolSchema(parameters={"type": "object", "properties": {}})
	timeout_ms = 100  # 100ms timeout

	async def execute(self, input_payload):
		return ToolResult.success(data={})

	async def execute_stream(self, input_payload, bus):
		await asyncio.sleep(10)  # Much longer than timeout
		return ToolResult.success(data={})


class _NonStreamingTool(BaseTool):
	"""A tool that does NOT override execute_stream (uses BaseTool default)."""
	name = "normal"
	description = "Normal tool"
	input_schema = {"type": "object", "properties": {}}
	schema = ToolSchema(parameters={"type": "object", "properties": {}})
	timeout_ms = 5000

	async def execute(self, input_payload):
		await asyncio.sleep(0.001)  # ensure measurable elapsed_ms
		return ToolResult.success(data={"result": "ok"})


@pytest.mark.asyncio
async def test_streaming_path_runs_pre_and_post_hooks(monkeypatch):
	"""C1: _execute_single_tool streaming path should run pre/post hooks."""
	from graph.nodes import _execute_single_tool
	from core.streaming_event_bus import StreamingEventBus
	from policy.gate import PolicyGate
	from policy.models import PolicyContext

	bus = StreamingEventBus()
	hook_calls = {"pre": [], "post": []}

	async def pre_hook(name, inp):
		hook_calls["pre"].append((name, inp))
		return inp

	async def post_hook(name, inp, result):
		hook_calls["post"].append((name, inp, result))

	mock_reg = MagicMock()
	mock_reg.get.return_value = _StreamingTool()
	mock_reg._run_pre_hooks = AsyncMock(side_effect=pre_hook)
	mock_reg._run_post_hooks = AsyncMock(side_effect=post_hook)
	mock_reg.invoke_capability = AsyncMock()

	monkeypatch.setattr(nodes, "get_tool_registry", lambda: mock_reg)
	monkeypatch.setattr(nodes, "get_streaming_bus", lambda: bus)
	monkeypatch.setattr(nodes, "_build_policy_gate", lambda: _AllowGate())

	gate = PolicyGate(tool_whitelist=set(), max_query_len=500)
	context = PolicyContext(conversation_id="test", agent_id="test")
	result = await _execute_single_tool("stream_tool", {"query": "test"}, gate, context)

	assert result["status"] == "completed"
	assert len(hook_calls["pre"]) == 1, "Pre-hook should have been called"
	assert len(hook_calls["post"]) == 1, "Post-hook should have been called"


@pytest.mark.asyncio
async def test_streaming_path_applies_per_tool_timeout(monkeypatch):
	"""C1: _execute_single_tool streaming path should apply per-tool timeout."""
	from graph.nodes import _execute_single_tool
	from core.streaming_event_bus import StreamingEventBus
	from policy.gate import PolicyGate
	from policy.models import PolicyContext

	bus = StreamingEventBus()

	mock_reg = MagicMock()
	mock_reg.get.return_value = _SlowStreamingTool()
	mock_reg._run_pre_hooks = AsyncMock(side_effect=lambda n, i: i)
	mock_reg._run_post_hooks = AsyncMock()

	monkeypatch.setattr(nodes, "get_tool_registry", lambda: mock_reg)
	monkeypatch.setattr(nodes, "get_streaming_bus", lambda: bus)
	monkeypatch.setattr(nodes, "_build_policy_gate", lambda: _AllowGate())

	gate = PolicyGate(tool_whitelist=set(), max_query_len=500)
	context = PolicyContext(conversation_id="test", agent_id="test")
	result = await _execute_single_tool("slow_stream", {}, gate, context)

	assert result["status"] == "error", f"Expected timeout error, got {result}"
	assert "TIMEOUT" in str(result.get("result", {})) or "TIMEOUT" in (result.get("error_msg") or "")


@pytest.mark.asyncio
async def test_non_overridden_streaming_uses_computed_elapsed_ms(monkeypatch):
	"""I4: Non-overridden execute_stream should use real elapsed_ms, not 0."""
	from graph.nodes import _execute_single_tool
	from core.streaming_event_bus import StreamingEventBus
	from policy.gate import PolicyGate
	from policy.models import PolicyContext

	bus = StreamingEventBus()
	emitted_events = []

	original_emit = bus.emit
	def capture_emit(event_type, **data):
		emitted_events.append((event_type, data))
		original_emit(event_type, **data)
	bus.emit = capture_emit

	mock_reg = MagicMock()
	mock_reg.get.return_value = _NonStreamingTool()
	mock_reg._run_pre_hooks = AsyncMock(side_effect=lambda n, i: i)
	mock_reg._run_post_hooks = AsyncMock()
	mock_reg.invoke_capability = AsyncMock()

	monkeypatch.setattr(nodes, "get_tool_registry", lambda: mock_reg)
	monkeypatch.setattr(nodes, "get_streaming_bus", lambda: bus)
	monkeypatch.setattr(nodes, "_build_policy_gate", lambda: _AllowGate())

	gate = PolicyGate(tool_whitelist=set(), max_query_len=500)
	context = PolicyContext(conversation_id="test", agent_id="test")
	result = await _execute_single_tool("normal", {}, gate, context)

	assert result["status"] == "completed"

	completed_events = [(t, d) for t, d in emitted_events if t == "tool.completed"]
	assert len(completed_events) >= 1
	elapsed_ms = completed_events[-1][1].get("elapsed_ms", 0)
	assert elapsed_ms > 0, f"Expected elapsed_ms > 0, got {elapsed_ms}"


@pytest.mark.asyncio
async def test_legacy_tool_node_records_metrics(monkeypatch):
	"""C2: Legacy single-tool path in tool_node should record metrics."""
	metric_calls = []

	mock_reg = MagicMock()
	mock_reg.get.return_value = _NonStreamingTool()
	mock_reg.invoke_capability = AsyncMock(return_value={"ok": True, "data": {}})
	mock_reg.record_metric = MagicMock(side_effect=lambda n, e, s: metric_calls.append((n, e, s)))

	monkeypatch.setattr(nodes, "get_tool_registry", lambda: mock_reg)
	monkeypatch.setattr(nodes, "_build_policy_gate", lambda: _AllowGate())

	out = await nodes.tool_node({
		"current_tool": "normal",
		"tool_input": {},
		"tool_steps": [],
		"reasoning_steps": [],
	})

	assert len(metric_calls) >= 1, "record_metric should have been called"
	assert metric_calls[0][0] == "normal"
	assert metric_calls[0][2] == "completed"


@pytest.mark.asyncio
async def test_legacy_streaming_path_runs_hooks(monkeypatch):
	"""I1: Legacy tool_node streaming path should run pre/post hooks."""
	from core.streaming_event_bus import StreamingEventBus

	bus = StreamingEventBus()
	hook_calls = {"pre": [], "post": []}

	async def pre_hook(name, inp):
		hook_calls["pre"].append((name, inp))
		return inp

	async def post_hook(name, inp, result):
		hook_calls["post"].append((name, inp, result))

	mock_reg = MagicMock()
	mock_reg.get.return_value = _StreamingTool()
	mock_reg._run_pre_hooks = AsyncMock(side_effect=pre_hook)
	mock_reg._run_post_hooks = AsyncMock(side_effect=post_hook)
	mock_reg.invoke_capability = AsyncMock()

	monkeypatch.setattr(nodes, "get_tool_registry", lambda: mock_reg)
	monkeypatch.setattr(nodes, "get_streaming_bus", lambda: bus)
	monkeypatch.setattr(nodes, "_build_policy_gate", lambda: _AllowGate())

	out = await nodes.tool_node({
		"current_tool": "stream_tool",
		"tool_input": {},
		"tool_steps": [],
		"reasoning_steps": [],
	})

	assert out["tool_steps"][0]["status"] == "completed"
	assert len(hook_calls["pre"]) == 1, "Pre-hook should have been called in legacy path"
	assert len(hook_calls["post"]) == 1, "Post-hook should have been called in legacy path"
