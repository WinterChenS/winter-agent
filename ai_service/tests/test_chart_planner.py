"""
Tests for chart planner node.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from graph.chart_planner import CHART_PLANNER_PROMPT, plan_chart


class TestChartPlannerPrompt:
    def test_prompt_is_non_empty(self):
        assert len(CHART_PLANNER_PROMPT) > 100

    def test_prompt_mentions_chart_types(self):
        for ct in ["line", "bar", "pie", "scatter", "area", "radar"]:
            assert ct in CHART_PLANNER_PROMPT.lower()

    def test_prompt_mentions_need_chart(self):
        assert "need_chart" in CHART_PLANNER_PROMPT

    def test_prompt_describes_when_chart_needed(self):
        assert "Trend analysis" in CHART_PLANNER_PROMPT or "trend" in CHART_PLANNER_PROMPT.lower()


class TestPlanChart:
    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.ainvoke = AsyncMock()
        return llm

    @pytest.mark.asyncio
    async def test_returns_need_chart_true(self, mock_llm):
        response = MagicMock()
        response.content = json.dumps({
            "need_chart": True,
            "chart_type": "bar",
            "reason": "comparing scores",
        })
        mock_llm.ainvoke.return_value = response

        result = await plan_chart(
            mock_llm,
            "compare scores",
            "GPT-4: 86.4\nClaude: 88.7\nGemini: 85.0",
        )
        assert result["need_chart"] is True
        assert result["chart_type"] == "bar"
        assert "comparing" in result["reason"]

    @pytest.mark.asyncio
    async def test_returns_need_chart_false(self, mock_llm):
        response = MagicMock()
        response.content = json.dumps({
            "need_chart": False,
            "chart_type": "",
            "reason": "no data to visualize",
        })
        mock_llm.ainvoke.return_value = response

        result = await plan_chart(mock_llm, "hello", "some text")
        assert result["need_chart"] is False

    @pytest.mark.asyncio
    async def test_empty_tool_results(self, mock_llm):
        result = await plan_chart(mock_llm, "hello", "")
        assert result["need_chart"] is False
        assert result["reason"] == "no tool results to analyze"
        mock_llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_only_tool_results(self, mock_llm):
        result = await plan_chart(mock_llm, "hello", "   \n  ")
        assert result["need_chart"] is False

    @pytest.mark.asyncio
    async def test_handles_markdown_code_block(self, mock_llm):
        response = MagicMock()
        response.content = '```json\n{"need_chart": true, "chart_type": "pie", "reason": "shares"}\n```'
        mock_llm.ainvoke.return_value = response

        result = await plan_chart(mock_llm, "shares", "data: 30%, 70%")
        assert result["need_chart"] is True
        assert result["chart_type"] == "pie"

    @pytest.mark.asyncio
    async def test_handles_pure_markdown_block(self, mock_llm):
        response = MagicMock()
        response.content = '```\n{"need_chart": true, "chart_type": "line", "reason": "trend"}\n```'
        mock_llm.ainvoke.return_value = response

        result = await plan_chart(mock_llm, "trend", "data: 1,2,3")
        assert result["need_chart"] is True
        assert result["chart_type"] == "line"

    @pytest.mark.asyncio
    async def test_handles_llm_error(self, mock_llm):
        mock_llm.ainvoke.side_effect = RuntimeError("LLM timeout")

        result = await plan_chart(mock_llm, "test", "some data")
        assert result["need_chart"] is False
        assert "error" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self, mock_llm):
        response = MagicMock()
        response.content = "not valid json at all"
        mock_llm.ainvoke.return_value = response

        result = await plan_chart(mock_llm, "test", "some data")
        assert result["need_chart"] is False

    @pytest.mark.asyncio
    async def test_handles_missing_chart_type(self, mock_llm):
        response = MagicMock()
        response.content = json.dumps({
            "need_chart": True,
            "reason": "has data",
        })
        mock_llm.ainvoke.return_value = response

        result = await plan_chart(mock_llm, "test", "data: 1,2,3")
        assert result["need_chart"] is True
        assert result["chart_type"] == ""

    @pytest.mark.asyncio
    async def test_truncates_long_tool_results(self, mock_llm):
        response = MagicMock()
        response.content = json.dumps({"need_chart": False, "chart_type": "", "reason": ""})
        mock_llm.ainvoke.return_value = response

        long_data = "x" * 5000
        result = await plan_chart(mock_llm, "test", long_data)
        assert result["need_chart"] is False
        # Verify truncation: message content should be <= 3000 chars
        call_args = mock_llm.ainvoke.call_args[0][0]
        tool_msg = [m for m in call_args if "Tool results" in m.content][0]
        assert len(tool_msg.content.split("Tool results: ")[1]) <= 3000
