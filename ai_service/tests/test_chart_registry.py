"""
Tests for ChartTypeRegistry and all 6 chart builders.
"""
from __future__ import annotations

import pytest

from charts import BaseChartBuilder, ChartTypeRegistry, chart_registry
from charts.types import (
    AreaChartBuilder,
    BarChartBuilder,
    LineChartBuilder,
    PieChartBuilder,
    RadarChartBuilder,
    ScatterChartBuilder,
)
from domain.chart_spec import ChartDataPoint, ChartSpec


def _make_spec(chart_type: str, data: list[ChartDataPoint] | None = None, **kwargs) -> ChartSpec:
    return ChartSpec(
        title="Test Chart",
        chart_type=chart_type,
        data=data or [ChartDataPoint(name="A", value=10), ChartDataPoint(name="B", value=20)],
        **kwargs,
    )


class TestBaseChartBuilder:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            BaseChartBuilder()  # type: ignore


class TestChartTypeRegistry:
    def test_register_and_list(self):
        reg = ChartTypeRegistry()
        reg.register(LineChartBuilder())
        reg.register(BarChartBuilder())
        assert set(reg.list_types()) == {"line", "bar"}

    def test_get_existing(self):
        reg = ChartTypeRegistry()
        reg.register(PieChartBuilder())
        assert reg.get("pie") is not None
        assert reg.get("pie").chart_type == "pie"  # type: ignore

    def test_get_missing_returns_none(self):
        reg = ChartTypeRegistry()
        assert reg.get("nonexistent") is None

    def test_build_echarts_option_uses_correct_builder(self):
        reg = ChartTypeRegistry()
        reg.register(BarChartBuilder())
        reg.register(PieChartBuilder())
        spec = _make_spec("pie")
        opt = reg.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "pie"

    def test_build_echarts_option_fallback_to_bar(self):
        reg = ChartTypeRegistry()
        reg.register(BarChartBuilder())
        spec = _make_spec("nonexistent_type")  # type: ignore
        opt = reg.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "bar"

    def test_build_echarts_option_absolute_fallback(self):
        reg = ChartTypeRegistry()
        spec = _make_spec("bar")
        opt = reg.build_echarts_option(spec)
        assert opt["xAxis"]["type"] == "category"


class TestLineChartBuilder:
    def test_basic_line_chart(self):
        builder = LineChartBuilder()
        spec = _make_spec("line")
        opt = builder.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "line"
        assert opt["series"][0]["smooth"] is True
        assert opt["xAxis"]["data"] == ["A", "B"]
        assert opt["xAxis"]["type"] == "category"

    def test_multi_series_line(self):
        builder = LineChartBuilder()
        spec = _make_spec("line", data=[
            ChartDataPoint(name="Q1", value=10, group="2023"),
            ChartDataPoint(name="Q1", value=15, group="2024"),
        ])
        opt = builder.build_echarts_option(spec)
        assert len(opt["series"]) == 2
        assert opt["series"][0]["name"] == "2023"
        assert opt["series"][1]["name"] == "2024"


class TestBarChartBuilder:
    def test_basic_bar_chart(self):
        builder = BarChartBuilder()
        spec = _make_spec("bar")
        opt = builder.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "bar"
        assert opt["xAxis"]["data"] == ["A", "B"]

    def test_bar_with_axis_labels(self):
        builder = BarChartBuilder()
        spec = _make_spec("bar", x_axis_label="Products", y_axis_label="Sales")
        opt = builder.build_echarts_option(spec)
        assert opt["xAxis"]["name"] == "Products"
        assert opt["yAxis"]["name"] == "Sales"


class TestPieChartBuilder:
    def test_basic_pie_chart(self):
        builder = PieChartBuilder()
        spec = _make_spec("pie")
        opt = builder.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "pie"
        assert len(opt["series"][0]["data"]) == 2
        assert opt["series"][0]["data"][0]["name"] == "A"

    def test_pie_has_emphasis(self):
        builder = PieChartBuilder()
        spec = _make_spec("pie")
        opt = builder.build_echarts_option(spec)
        emphasis = opt["series"][0].get("emphasis", {})
        assert "itemStyle" in emphasis


class TestScatterChartBuilder:
    def test_basic_scatter_chart(self):
        builder = ScatterChartBuilder()
        spec = _make_spec("scatter")
        opt = builder.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "scatter"
        assert opt["xAxis"]["type"] == "value"
        assert opt["yAxis"]["type"] == "value"

    def test_scatter_multi_series(self):
        builder = ScatterChartBuilder()
        spec = _make_spec("scatter", data=[
            ChartDataPoint(name="X", value=1, group="G1"),
            ChartDataPoint(name="X", value=2, group="G2"),
        ])
        opt = builder.build_echarts_option(spec)
        assert len(opt["series"]) == 2


class TestAreaChartBuilder:
    def test_basic_area_chart(self):
        builder = AreaChartBuilder()
        spec = _make_spec("area")
        opt = builder.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "line"
        assert "areaStyle" in opt["series"][0]


class TestRadarChartBuilder:
    def test_basic_radar_chart(self):
        builder = RadarChartBuilder()
        spec = _make_spec("radar")
        opt = builder.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "radar"
        assert "radar" in opt

    def test_radar_indicators(self):
        builder = RadarChartBuilder()
        spec = _make_spec("radar", data=[
            ChartDataPoint(name="Speed", value=80),
            ChartDataPoint(name="Power", value=60),
        ])
        opt = builder.build_echarts_option(spec)
        assert len(opt["radar"]["indicator"]) == 2
        assert opt["radar"]["indicator"][0]["name"] == "Speed"


class TestGlobalRegistry:
    def test_global_registry_is_singleton(self):
        from charts import chart_registry as cr1
        from charts import chart_registry as cr2
        assert cr1 is cr2

    def test_fallback_option_has_required_keys(self):
        spec = _make_spec("bar")
        opt = chart_registry.build_echarts_option(spec)
        assert "title" in opt
        assert "xAxis" in opt
        assert "yAxis" in opt
        assert "series" in opt
