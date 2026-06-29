"""Tests for ChartSpec v2 -- the single source of truth for chart data."""
from __future__ import annotations

import json

import pytest

from chart.chart_spec import ChartSpec, SeriesSpec, SliceSpec, PointSpec


class TestSeriesSpec:
    def test_create_minimal(self):
        s = SeriesSpec(name="GDP", color="#2F80ED", color_name="蓝色", values=[1, 2, 3])
        assert s.name == "GDP"
        assert s.color == "#2F80ED"
        assert s.color_name == "蓝色"
        assert s.values == [1, 2, 3]


class TestSliceSpec:
    def test_create_minimal(self):
        s = SliceSpec(label="A", value=30.0, color="#EB5757", color_name="红色")
        assert s.label == "A"
        assert s.value == 30.0
        assert s.color_name == "红色"


class TestPointSpec:
    def test_create_without_label(self):
        p = PointSpec(x=1.0, y=2.0)
        assert p.x == 1.0
        assert p.y == 2.0
        assert p.label is None

    def test_create_with_label(self):
        p = PointSpec(x=1.0, y=2.0, label="peak")
        assert p.label == "peak"


class TestChartSpec:
    def test_create_bar_spec(self):
        spec = ChartSpec(
            title="Sales",
            chart_type="bar",
            xlabel="Quarter",
            ylabel="Revenue",
            series=[
                SeriesSpec(name="Q1", color="#2F80ED", color_name="蓝色", values=[100]),
            ],
        )
        assert spec.title == "Sales"
        assert spec.chart_type == "bar"
        assert spec.xlabel == "Quarter"
        assert spec.ylabel == "Revenue"

    def test_create_pie_spec(self):
        spec = ChartSpec(
            title="Market Share",
            chart_type="pie",
            slices=[
                SliceSpec(label="A", value=30, color="#2F80ED", color_name="蓝色"),
                SliceSpec(label="B", value=70, color="#EB5757", color_name="红色"),
            ],
        )
        assert len(spec.slices) == 2

    def test_create_scatter_spec(self):
        spec = ChartSpec(
            title="Scatter",
            chart_type="scatter",
            points=[PointSpec(x=1, y=2), PointSpec(x=3, y=4)],
        )
        assert len(spec.points) == 2

    def test_default_figsize(self):
        spec = ChartSpec(title="T", chart_type="bar", series=[SeriesSpec("X", "#000", "", [])])
        assert spec.figsize == (12, 6)

    def test_color_name_auto_fill(self):
        spec = ChartSpec(
            title="AutoFill",
            chart_type="bar",
            series=[
                SeriesSpec(name="S1", color="#2F80ED", color_name="", values=[10]),
            ],
        )
        assert spec.series[0].color_name == "蓝色"


class TestToMetadata:
    def test_bar_metadata(self):
        spec = ChartSpec(
            title="Sales",
            chart_type="bar",
            xlabel="Quarter",
            ylabel="Revenue",
            figsize=(10, 5),
            series=[
                SeriesSpec(name="Q1", color="#2F80ED", color_name="蓝色", values=[100, 200]),
            ],
        )
        meta = spec.to_metadata()
        assert meta["title"] == "Sales"
        assert meta["chart_type"] == "bar"
        assert meta["xlabel"] == "Quarter"
        assert meta["ylabel"] == "Revenue"
        assert meta["figsize"] == [10, 5]
        assert len(meta["series"]) == 1
        assert meta["series"][0]["name"] == "Q1"
        assert meta["series"][0]["color"] == "#2F80ED"
        assert meta["series"][0]["color_name"] == "蓝色"

    def test_pie_metadata(self):
        spec = ChartSpec(
            title="Pie",
            chart_type="pie",
            slices=[
                SliceSpec(label="A", value=30, color="#EB5757", color_name="红色"),
            ],
        )
        meta = spec.to_metadata()
        assert meta["chart_type"] == "pie"
        assert meta["slices"][0]["label"] == "A"

    def test_metadata_json_serializable(self):
        spec = ChartSpec(
            title="JSON",
            chart_type="bar",
            series=[SeriesSpec("S", "#2F80ED", "蓝色", [1, 2])],
        )
        json_str = json.dumps(spec.to_metadata(), ensure_ascii=False)
        assert isinstance(json_str, str)


class TestAllValues:
    def test_bar_values(self):
        spec = ChartSpec(
            title="T", chart_type="bar",
            series=[
                SeriesSpec("A", "#000", "", [1, 2, 3]),
                SeriesSpec("B", "#111", "", [4, 5]),
            ],
        )
        assert spec.all_values() == [1, 2, 3, 4, 5]

    def test_pie_values(self):
        spec = ChartSpec(
            title="T", chart_type="pie",
            slices=[
                SliceSpec("A", 30.0, "#000", ""),
                SliceSpec("B", 70.0, "#111", ""),
            ],
        )
        assert spec.all_values() == [30.0, 70.0]

    def test_empty_returns_empty_list(self):
        spec = ChartSpec(title="T", chart_type="bar")
        assert spec.all_values() == []
