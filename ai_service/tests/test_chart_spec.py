"""Tests for ChartSpec data model."""
from __future__ import annotations

import json

from domain.chart_spec import (
    CHART_SPEC_JSON_SCHEMA,
    ChartDataPoint,
    ChartSpec,
)


class TestChartDataPoint:
    def test_create_default(self):
        dp = ChartDataPoint(name="GPT-4", value=86.4)
        assert dp.name == "GPT-4"
        assert dp.value == 86.4
        assert dp.group == ""

    def test_create_with_group(self):
        dp = ChartDataPoint(name="GPT-4", value=86.4, group="MMLU")
        assert dp.group == "MMLU"

    def test_int_value(self):
        dp = ChartDataPoint(name="count", value=42)
        assert dp.value == 42
        assert isinstance(dp.value, int)


class TestChartSpec:
    def test_create_minimal(self):
        spec = ChartSpec(title="Test", chart_type="bar", data=[])
        assert spec.title == "Test"
        assert spec.chart_type == "bar"
        assert len(spec.data) == 0
        assert len(spec.id) == 12

    def test_to_dict_basic(self):
        spec = ChartSpec(
            title="AI Scores",
            chart_type="bar",
            description="Model comparison",
            x_axis_label="Model",
            y_axis_label="Score",
            data=[
                ChartDataPoint(name="GPT-4", value=86.4),
                ChartDataPoint(name="Claude", value=88.7, group="Anthropic"),
            ],
        )
        d = spec.to_dict()
        assert d["title"] == "AI Scores"
        assert d["chartType"] == "bar"
        assert d["description"] == "Model comparison"
        assert d["xAxisLabel"] == "Model"
        assert d["yAxisLabel"] == "Score"
        assert len(d["data"]) == 2
        assert d["data"][0]["name"] == "GPT-4"
        assert d["data"][0]["value"] == 86.4
        assert d["data"][0]["group"] == ""
        assert d["data"][1]["group"] == "Anthropic"

    def test_from_dict_roundtrip(self):
        original = ChartSpec(
            title="Roundtrip",
            chart_type="pie",
            description="Test",
            data=[ChartDataPoint(name="A", value=30, group="g1")],
        )
        restored = ChartSpec.from_dict(original.to_dict())
        assert restored.title == original.title
        assert restored.chart_type == original.chart_type
        assert len(restored.data) == 1
        assert restored.data[0].name == "A"
        assert restored.data[0].value == 30

    def test_from_dict_partial(self):
        spec = ChartSpec.from_dict({"title": "Partial", "chartType": "line", "data": []})
        assert spec.title == "Partial"
        assert spec.chart_type == "line"
        assert len(spec.id) == 12

    def test_from_dict_defaults(self):
        spec = ChartSpec.from_dict({})
        assert spec.title == ""
        assert spec.chart_type == "bar"
        assert len(spec.data) == 0

    def test_json_serializable(self):
        spec = ChartSpec(
            title="JSON Test",
            chart_type="line",
            data=[ChartDataPoint(name="X", value=1.5)],
        )
        json_str = json.dumps(spec.to_dict())
        parsed = json.loads(json_str)
        assert parsed["title"] == "JSON Test"
        assert parsed["data"][0]["value"] == 1.5


class TestChartSpecJsonSchema:
    def test_schema_required_fields(self):
        assert "title" in CHART_SPEC_JSON_SCHEMA["required"]
        assert "chartType" in CHART_SPEC_JSON_SCHEMA["required"]
        assert "data" in CHART_SPEC_JSON_SCHEMA["required"]

    def test_schema_chart_types(self):
        types = CHART_SPEC_JSON_SCHEMA["properties"]["chartType"]["enum"]
        assert "line" in types
        assert "bar" in types
        assert "pie" in types
        assert "scatter" in types
        assert "area" in types
        assert "radar" in types

    def test_schema_data_items(self):
        props = CHART_SPEC_JSON_SCHEMA["properties"]["data"]["items"]["properties"]
        assert "name" in props
        assert "value" in props
        assert "group" in props
