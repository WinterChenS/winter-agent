"""
Tests for ChartSpec and ChartDataPoint data models.
"""
from __future__ import annotations

import json

from domain.chart_spec import (
    CHART_SPEC_JSON_SCHEMA,
    ChartDataPoint,
    ChartSpec,
    ChartType,
)


class TestChartDataPoint:
    def test_create_with_defaults(self):
        dp = ChartDataPoint(name="Samsung", value=20.8)
        assert dp.name == "Samsung"
        assert dp.value == 20.8
        assert dp.group == ""

    def test_create_with_group(self):
        dp = ChartDataPoint(name="Q1", value=100, group="2024")
        assert dp.name == "Q1"
        assert dp.value == 100
        assert dp.group == "2024"

    def test_int_value(self):
        dp = ChartDataPoint(name="A", value=42)
        assert dp.value == 42
        assert isinstance(dp.value, int)


class TestChartSpec:
    def test_create_minimal(self):
        spec = ChartSpec(title="Test Chart", chart_type="bar")
        assert spec.title == "Test Chart"
        assert spec.chart_type == "bar"
        assert spec.id != ""
        assert len(spec.id) == 12
        assert spec.data == []

    def test_create_with_data(self):
        spec = ChartSpec(
            title="Market Share",
            chart_type="pie",
            description="Q1 2026 smartphone market share",
            x_axis_label="Brand",
            y_axis_label="Share %",
            data=[
                ChartDataPoint(name="Samsung", value=20.8),
                ChartDataPoint(name="Apple", value=17.3),
            ],
        )
        assert len(spec.data) == 2
        assert spec.description == "Q1 2026 smartphone market share"

    def test_defaults(self):
        spec = ChartSpec()
        assert spec.title == ""
        assert spec.chart_type == "bar"
        assert spec.description == ""
        assert spec.x_axis_label == ""
        assert spec.y_axis_label == ""
        assert spec.data == []

    def test_unique_id_per_instance(self):
        s1 = ChartSpec(title="A")
        s2 = ChartSpec(title="B")
        assert s1.id != s2.id

    def test_to_dict_basic(self):
        spec = ChartSpec(
            title="Test",
            chart_type="line",
            data=[ChartDataPoint(name="X", value=10.5, group="G1")],
        )
        d = spec.to_dict()
        assert d["title"] == "Test"
        assert d["chartType"] == "line"
        assert len(d["data"]) == 1
        assert d["data"][0]["name"] == "X"
        assert d["data"][0]["value"] == 10.5
        assert d["data"][0]["group"] == "G1"
        assert "id" in d
        assert "description" in d

    def test_to_dict_serializable(self):
        spec = ChartSpec(
            title="T",
            data=[ChartDataPoint(name="A", value=1)],
        )
        d = spec.to_dict()
        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert "chartType" in json_str

    def test_from_dict_minimal(self):
        d = {"title": "From Dict", "chartType": "pie", "data": []}
        spec = ChartSpec.from_dict(d)
        assert spec.title == "From Dict"
        assert spec.chart_type == "pie"
        assert spec.data == []

    def test_from_dict_with_data(self):
        d = {
            "title": "Scores",
            "chartType": "bar",
            "data": [
                {"name": "GPT-4", "value": 86.4},
                {"name": "Claude", "value": 88.7, "group": "Anthropic"},
            ],
        }
        spec = ChartSpec.from_dict(d)
        assert len(spec.data) == 2
        assert spec.data[0].name == "GPT-4"
        assert spec.data[0].value == 86.4
        assert spec.data[0].group == ""
        assert spec.data[1].name == "Claude"
        assert spec.data[1].value == 88.7
        assert spec.data[1].group == "Anthropic"

    def test_from_dict_defaults_missing_fields(self):
        spec = ChartSpec.from_dict({})
        assert spec.title == ""
        assert spec.chart_type == "bar"

    def test_from_dict_generates_id(self):
        spec = ChartSpec.from_dict({"title": "X", "chartType": "bar", "data": []})
        assert len(spec.id) == 12

    def test_from_dict_preserves_id(self):
        spec = ChartSpec.from_dict(
            {"id": "custom12345", "title": "X", "chartType": "bar", "data": []}
        )
        assert spec.id == "custom12345"

    def test_roundtrip_to_from_dict(self):
        original = ChartSpec(
            title="Roundtrip",
            chart_type="scatter",
            description="Test",
            data=[
                ChartDataPoint(name="A", value=1, group="g"),
                ChartDataPoint(name="B", value=2),
            ],
        )
        restored = ChartSpec.from_dict(original.to_dict())
        assert restored.title == original.title
        assert restored.chart_type == original.chart_type
        assert restored.id == original.id
        assert len(restored.data) == len(original.data)
        assert restored.data[0].name == original.data[0].name
        assert restored.data[0].value == original.data[0].value
        assert restored.data[0].group == original.data[0].group

    def test_all_chart_types_accepted(self):
        for ct in ["line", "bar", "pie", "scatter", "area", "radar"]:
            spec = ChartSpec(title=ct, chart_type=ct)
            assert spec.chart_type == ct


class TestChartSpecJsonSchema:
    def test_required_fields(self):
        assert "title" in CHART_SPEC_JSON_SCHEMA["required"]
        assert "chartType" in CHART_SPEC_JSON_SCHEMA["required"]
        assert "data" in CHART_SPEC_JSON_SCHEMA["required"]

    def test_chart_type_enum_covers_all_six(self):
        enum = CHART_SPEC_JSON_SCHEMA["properties"]["chartType"]["enum"]
        assert set(enum) == {"line", "bar", "pie", "scatter", "area", "radar"}

    def test_data_items_required_name_value(self):
        items = CHART_SPEC_JSON_SCHEMA["properties"]["data"]["items"]
        assert "name" in items["required"]
        assert "value" in items["required"]

    def test_schema_is_valid_json(self):
        json.dumps(CHART_SPEC_JSON_SCHEMA)
