"""Tests for chart generator (mock LLM)."""
from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from graph.chart_generator import CHART_GENERATOR_PROMPT, generate_chart_spec


def _mock_llm(resp_dict):
    llm = MagicMock()
    r = MagicMock()
    r.content = json.dumps(resp_dict)
    llm.ainvoke = AsyncMock(return_value=r)
    return llm


class TestPrompt:
    def test_has_schema_fields(self):
        for f in ["chartType", "title", "data"]:
            assert f in CHART_GENERATOR_PROMPT, f"missing {f}"


class TestGenerateChartSpec:
    @pytest.mark.asyncio
    async def test_no_chart_intent(self):
        result = await generate_chart_spec(MagicMock(), "msg", "data",
                                           {"need_chart": False, "chart_type": ""})
        assert result is None

    @pytest.mark.asyncio
    async def test_generates_bar_chart(self):
        llm = _mock_llm({
            "title": "Scores", "chartType": "bar", "data": [
                {"name": "GPT-4", "value": 86.4}, {"name": "Claude", "value": 88.7}]})
        r = await generate_chart_spec(llm, "compare", "data",
                                      {"need_chart": True, "chart_type": "bar", "reason": ""})
        assert r is not None
        assert r["title"] == "Scores"
        assert r["chartType"] == "bar"
        assert len(r["data"]) == 2
        assert r["data"][0]["name"] == "GPT-4"
        assert r["data"][0]["value"] == 86.4

    @pytest.mark.asyncio
    async def test_overrides_chart_type(self):
        llm = _mock_llm({"title": "P", "chartType": "bar", "data": [{"name": "A", "value": 30}]})
        r = await generate_chart_spec(llm, "shares", "data",
                                      {"need_chart": True, "chart_type": "pie", "reason": ""})
        assert r["chartType"] == "pie"

    @pytest.mark.asyncio
    async def test_llm_error(self):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=Exception("fail"))
        r = await generate_chart_spec(llm, "test", "data",
                                      {"need_chart": True, "chart_type": "bar", "reason": ""})
        assert r is None

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        llm = MagicMock()
        r = MagicMock()
        r.content = "bad json"
        llm.ainvoke = AsyncMock(return_value=r)
        result = await generate_chart_spec(llm, "test", "data",
                                           {"need_chart": True, "chart_type": "line", "reason": ""})
        assert result is None

    @pytest.mark.asyncio
    async def test_markdown_fence(self):
        llm = MagicMock()
        r = MagicMock()
        r.content = '```json\n{"title": "T", "chartType": "line", "data": [{"name": "X", "value": 1}]}\n```'
        llm.ainvoke = AsyncMock(return_value=r)
        result = await generate_chart_spec(llm, "test", "data",
                                           {"need_chart": True, "chart_type": "line", "reason": ""})
        assert result is not None
        assert result["chartType"] == "line"

    @pytest.mark.asyncio
    async def test_grouped_data(self):
        llm = _mock_llm({
            "title": "Groups", "chartType": "bar",
            "data": [{"name": "A", "value": 10, "group": "G1"},
                     {"name": "A", "value": 15, "group": "G2"}]})
        r = await generate_chart_spec(llm, "test", "data",
                                      {"need_chart": True, "chart_type": "bar", "reason": ""})
        assert len(r["data"]) == 2
        assert r["data"][0]["group"] == "G1"
