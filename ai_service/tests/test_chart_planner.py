from __future__ import annotations
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from graph.chart_planner import CHART_PLANNER_PROMPT, plan_charts

class TestPrompt:
    def test_has_chart_types(self):
        assert "line" in CHART_PLANNER_PROMPT

    def test_has_charts_array(self):
        assert '"charts"' in CHART_PLANNER_PROMPT

    def test_has_scenarios(self):
        assert "trend" in CHART_PLANNER_PROMPT.lower()

class TestPlanCharts:
    @pytest.mark.asyncio
    async def test_empty_tool_results(self):
        result = await plan_charts(MagicMock(), "test", "")
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_tool_results(self):
        result = await plan_charts(MagicMock(), "test", "   ")
        assert result == []

    @pytest.mark.asyncio
    async def test_single_chart_new_format(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = json.dumps({"charts": [{"chart_type": "bar", "reason": "compare prices"}]})
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_charts(llm, "compare prices", "A: 10, B: 20")
        assert len(result) == 1
        assert result[0]["chart_type"] == "bar"

    @pytest.mark.asyncio
    async def test_multi_chart(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = json.dumps({"charts": [
            {"chart_type": "line", "reason": "trend"},
            {"chart_type": "pie", "reason": "ratio"}
        ]})
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_charts(llm, "show trend and ratio", "A: 10, B: 20, C: 30")
        assert len(result) == 2
        assert result[0]["chart_type"] == "line"
        assert result[1]["chart_type"] == "pie"

    @pytest.mark.asyncio
    async def test_no_charts_needed(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = json.dumps({"charts": []})
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_charts(llm, "hello", "no data here")
        assert result == []

    @pytest.mark.asyncio
    async def test_legacy_format_fallback(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = json.dumps({"need_chart": True, "chart_type": "pie", "reason": "shares"})
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_charts(llm, "shares", "A: 30%, B: 70%")
        assert len(result) == 1
        assert result[0]["chart_type"] == "pie"

    @pytest.mark.asyncio
    async def test_llm_error(self):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=Exception("API down"))
        result = await plan_charts(llm, "test", "1,2,3")
        assert result == []

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = "not json at all"
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_charts(llm, "test", "data")
        assert result == []

    @pytest.mark.asyncio
    async def test_long_data_truncation(self):
        llm = MagicMock()
        resp = MagicMock()
        resp.content = json.dumps({"charts": [{"chart_type": "line", "reason": "ok"}]})
        llm.ainvoke = AsyncMock(return_value=resp)
        result = await plan_charts(llm, "trend", "x" * 5000)
        assert len(result) == 1
