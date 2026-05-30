"""
Tests for chart generator node.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from graph.chart_generator import CHART_GENERATOR_PROMPT, generate_chart_spec


class TestChartGeneratorPrompt:
    def test_prompt_is_non_empty(self):
        assert len(CHART_GENERATOR_PROMPT) > 100

    def test_prompt_includes_json_schema(self):
        assert "chartType" in CHART_GENERATOR_PROMPT
        assert "title" in CHART_GENERATOR_PROMPT
        assert "data" in CHART_GENERATOR_PROMPT

    def test_prompt_mentions_rules(self):
        assert "numerical data" in CHART_GENERATOR_PROMPT.lower()


class TestGenerateChartSpec:
    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.ainvoke = AsyncMock()
        return llm

    @pytest.mark.asyncio
    async def test_returns_none_when_need_chart_false(self, mock_llm):
        intent = {"need_chart": False, "chart_type": "bar", "reason": ""}
        result = await generate_chart_spec(mock_llm, "test", "data", intent)
        assert result is None
        mock_llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_generates_bar_chart_spec(self, mock_llm):
        response = MagicMock()
        response.content = json.dumps({
            "title": "Scores",
            "chartType": "bar",
            "description": "Comparison",
            "data": [
                {"name": "GPT-4", "value": 86.4},
                {"name": "Claude", "value": 88.7},
            ],
        })
        mock_llm.ainvoke.return_value = response

        intent = {"need_chart": True, "chart_type": "bar", "reason": "compare"}
        result = await generate_chart_spec(mock_llm, "compare", "GPT-4: 86.4", intent)

        assert result is not None
        assert result["chartType"] == "bar"
        assert result["title"] == "Scores"
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "GPT-4"
        assert result["data"][0]["value"] == 86.4

    @pytest.mark.asyncio
    async def test_overrides_chart_type_from_intent(self, mock_llm):
        response = MagicMock()
        response.content = json.dumps({
            "title": "Pie",
            "chartType": "bar",  # LLM returned bar, but intent says pie
            "data": [{"name": "A", "value": 50}, {"name": "B", "value": 50}],
        })
        mock_llm.ainvoke.return_value = response

        intent = {"need_chart": True, "chart_type": "pie", "reason": "proportions"}
        result = await generate_chart_spec(mock_llm, "test", "data", intent)

        assert result["chartType"] == "pie"  # Overridden by intent

    @pytest.mark.asyncio
    async def test_handles_markdown_code_block(self, mock_llm):
        response = MagicMock()
        response.content = '```json\n{"title": "Test", "chartType": "line", "data": [{"name": "X", "value": 1}]}\n```'
        mock_llm.ainvoke.return_value = response

        intent = {"need_chart": True, "chart_type": "line", "reason": "trend"}
        result = await generate_chart_spec(mock_llm, "test", "data", intent)

        assert result is not None
        assert result["chartType"] == "line"

    @pytest.mark.asyncio
    async def test_handles_generic_code_block(self, mock_llm):
        response = MagicMock()
        response.content = '```\n{"title": "T", "chartType": "bar", "data": []}\n```'
        mock_llm.ainvoke.return_value = response

        intent = {"need_chart": True, "chart_type": "bar", "reason": ""}
        result = await generate_chart_spec(mock_llm, "test", "data", intent)

        assert result is not None
        assert result["chartType"] == "bar"

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self, mock_llm):
        mock_llm.ainvoke.side_effect = RuntimeError("LLM failed")

        intent = {"need_chart": True, "chart_type": "bar", "reason": ""}
        result = await generate_chart_spec(mock_llm, "test", "data", intent)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self, mock_llm):
        response = MagicMock()
        response.content = "not json at all"
        mock_llm.ainvoke.return_value = response

        intent = {"need_chart": True, "chart_type": "bar", "reason": ""}
        result = await generate_chart_spec(mock_llm, "test", "data", intent)

        assert result is None

    @pytest.mark.asyncio
    async def test_includes_description_in_result(self, mock_llm):
        response = MagicMock()
        response.content = json.dumps({
            "title": "Chart",
            "chartType": "bar",
            "description": "A detailed description",
            "xAxisLabel": "Models",
            "yAxisLabel": "Score",
            "data": [{"name": "A", "value": 1}],
        })
        mock_llm.ainvoke.return_value = response

        intent = {"need_chart": True, "chart_type": "bar", "reason": ""}
        result = await generate_chart_spec(mock_llm, "test", "data", intent)

        assert result["description"] == "A detailed description"
        assert result["xAxisLabel"] == "Models"
        assert result["yAxisLabel"] == "Score"

    @pytest.mark.asyncio
    async def test_generates_id(self, mock_llm):
        response = MagicMock()
        response.content = json.dumps({
            "title": "T",
            "chartType": "bar",
            "data": [{"name": "A", "value": 1}],
        })
        mock_llm.ainvoke.return_value = response

        intent = {"need_chart": True, "chart_type": "bar", "reason": ""}
        result = await generate_chart_spec(mock_llm, "test", "data", intent)

        assert "id" in result
        assert len(result["id"]) == 12
