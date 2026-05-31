from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

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
async def test_duplicate_search_is_forced_to_final_answer(monkeypatch):
    llm = _DummyLLM(
        responses=[
            '{"action":"tool","tool":"search","query":"2026-05-24 今日新闻"}',
            "基于已有检索结果：今天主要新闻包括...",
        ]
    )
    monkeypatch.setattr(nodes, "_build_llm", lambda streaming=True, json_mode=False: llm)
    monkeypatch.setattr(nodes, "get_tool_registry", lambda: None)

    state = {
        "messages": [HumanMessage(content="今天有什么新闻")],
        "tool_result": '{"ok": true, "data": {"query": "2026-05-24 今日新闻", "results": [{"title": "t1", "url": "https://a.com"}]}}',
        "iteration_count": 1,
        "last_tool_name": "search",
        "last_tool_query": "2026-05-24 今日新闻",
        "reasoning_steps": [],
    }

    out = await nodes.agent_node(state)

    assert out["current_tool"] is None
    assert out["tool_input"] is None
    assert out["route"] == "chart_planner"
    assert out["last_guard_reason"]["code"] == "DUPLICATE_TOOL_CALL_BLOCKED"
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_search_with_existing_hits_skips_new_search(monkeypatch):
    llm = _DummyLLM(
        responses=[
            '{"action":"tool","tool":"search","query":"2026-05-24 A股新闻"}',
            "我已基于已检索到的信息整理如下...",
        ]
    )
    monkeypatch.setattr(nodes, "_build_llm", lambda streaming=True, json_mode=False: llm)
    monkeypatch.setattr(nodes, "get_tool_registry", lambda: None)

    state = {
        "messages": [HumanMessage(content="今天A股新闻")],
        "tool_result": '{"ok": true, "data": {"query": "2026-05-24 今日新闻", "results": [{"title": "t1", "url": "https://a.com"}]}}',
        "iteration_count": 1,
        "last_tool_name": "time",
        "last_tool_query": "",
        "reasoning_steps": [],
    }

    out = await nodes.agent_node(state)

    # Guard SEARCH_RESULTS_ALREADY_AVAILABLE was intentionally removed
    # to allow the ReAct loop to continue with different search queries.
    # The LLM can now proceed with a new search even when previous search had hits.
    assert out["current_tool"] == "search"
    assert out["tool_input"] == {"query": "2026-05-24 A股新闻"}
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_max_consecutive_search_guard_forces_final_answer(monkeypatch):
    llm = _DummyLLM(
        responses=[
            '{"action":"tool","tool":"search","query":"A股实时新闻"}',
            "下面是基于已有检索证据的最终汇总...",
        ]
    )
    monkeypatch.setattr(nodes, "_build_llm", lambda streaming=True, json_mode=False: llm)
    monkeypatch.setattr(nodes, "get_tool_registry", lambda: None)
    monkeypatch.setattr(nodes.settings, "max_consecutive_search_calls", 2, raising=False)

    state = {
        "messages": [HumanMessage(content="继续查最新A股新闻")],
        "tool_result": '{"ok": true, "data": {"query": "A股新闻", "results": []}}',
        "iteration_count": 2,
        "last_tool_name": "time",
        "last_tool_query": "",
        "consecutive_search_count": 2,
        "reasoning_steps": [],
    }

    out = await nodes.agent_node(state)

    assert out["current_tool"] is None
    assert out["tool_input"] is None
    assert out["consecutive_search_count"] == 0
    assert out["last_guard_reason"]["code"] == "MAX_CONSECUTIVE_SEARCH_REACHED"
    assert isinstance(out["reasoning_steps"][-1], dict)
    assert out["reasoning_steps"][-1]["code"] == "MAX_CONSECUTIVE_SEARCH_REACHED"
    assert out["route"] == "chart_planner"
    assert llm.calls == 1


