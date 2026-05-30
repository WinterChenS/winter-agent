"""Tests for chart planner (mock LLM)."""
from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from graph.chart_planner import CHART_PLANNER_PROMPT, plan_chart


class TestPrompt:
    def test_has_chart_types(self):
        for ct in ["line", "bar", "pie", "scatter", "area", "radar"]:
            assert ct in CHART_PLANNER_PROMPT, f"missing {ct}"

    def test_has_need_chart(self):
        assert "need_chart" in CHART_PLANNER_PROMPT

    def test_has_scenarios(self):
        lower = CHART_PLANNER_PROMPT.lower()
        for kw in ["trend", "comparison", "proportion"]:
            assert kw in lower, f"missing {kw}"


class TestPlanChart:
    @pytest.mark.asyncio
    async def test_empty_tool_results(self):
        llm = MagicMock()
        result = await plan_chart(llm, "msg", "")
        assert result["need_chart"] is False
        assert result["chart_type"] == ""

    @pytest.mark.asyncio
    async def test_whitespace_tool_results(self):
        llm = MagicMock()
        result = await plan_chart(llm, "msg", "   ")
        assert result["need_chart"] is False

    @pytest.mark.asyncio
    async def test_need_chart_true(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = json.dumps({"need_chart": True, "chart_type": "bar", "reason": "comparing"})
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_chart(llm, "compare", "GPT-4: 86, Claude: 88")
        assert result["need_chart"] is True
        assert result["chart_type"] == "bar"

    @pytest.mark.asyncio
    async def test_need_chart_false(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = json.dumps({"need_chart": False, "chart_type": "", "reason": "no data"})
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_chart(llm, "what is AI", "AI is intelligence")
        assert result["need_chart"] is False

    @pytest.mark.asyncio
    async def test_markdown_fence(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = '```json\n{"need_chart": true, "chart_type": "pie", "reason": "shares"}\n```'
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_chart(llm, "shares", "A: 30%, B: 70%")
        assert result["need_chart"] is True
        assert result["chart_type"] == "pie"

    @pytest.mark.asyncio
    async def test_llm_error(self):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=Exception("API down"))
        result = await plan_chart(llm, "test", "1,2,3")
        assert result["need_chart"] is False
        assert "planner error" in result["reason"]

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = "not json at all"
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_chart(llm, "test", "data")
        assert result["need_chart"] is False

    @pytest.mark.asyncio
    async def test_long_data_truncation(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = json.dumps({"need_chart": True, "chart_type": "line", "reason": "ok"})
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_chart(llm, "trend", "x" * 5000)
        assert result["need_chart"] is True
        assert llm.ainvoke.called
