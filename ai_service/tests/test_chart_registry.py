"""Tests for chart type plugin registry and builders."""
from __future__ import annotations

from charts import ChartTypeRegistry, chart_registry
from charts.types import (
    AreaChartBuilder, BarChartBuilder, LineChartBuilder,
    PieChartBuilder, RadarChartBuilder, ScatterChartBuilder,
)
from domain.chart_spec import ChartDataPoint, ChartSpec


class TestChartTypeRegistry:
    def test_register_and_get(self):
        reg = ChartTypeRegistry()
        reg.register(BarChartBuilder())
        b = reg.get("bar")
        assert b is not None
        assert b.chart_type == "bar"

    def test_get_missing(self):
        reg = ChartTypeRegistry()
        assert reg.get("nope") is None

    def test_list_types(self):
        reg = ChartTypeRegistry()
        reg.register(LineChartBuilder())
        reg.register(BarChartBuilder())
        types = reg.list_types()
        assert "line" in types
        assert "bar" in types

    def test_fallback_to_bar(self):
        reg = ChartTypeRegistry()
        reg.register(BarChartBuilder())
        spec = ChartSpec(title="F", chart_type="nope", data=[ChartDataPoint(name="A", value=10)])
        opt = reg.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "bar"

    def test_total_fallback(self):
        reg = ChartTypeRegistry()
        spec = ChartSpec(title="F", chart_type="line", data=[ChartDataPoint(name="A", value=10)])
        opt = reg.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "bar"

    def test_global_registry(self):
        assert isinstance(chart_registry, ChartTypeRegistry)


class TestLineChartBuilder:
    def test_basic(self):
        b = LineChartBuilder()
        spec = ChartSpec(title="T", chart_type="line", data=[
            ChartDataPoint(name="Jan", value=10), ChartDataPoint(name="Feb", value=20)])
        opt = b.build_echarts_option(spec)
        assert opt["xAxis"]["data"] == ["Jan", "Feb"]
        assert opt["series"][0]["type"] == "line"
        assert opt["series"][0]["smooth"] is True

    def test_multi_series(self):
        b = LineChartBuilder()
        spec = ChartSpec(title="M", chart_type="line", data=[
            ChartDataPoint(name="Jan", value=10, group="A"),
            ChartDataPoint(name="Jan", value=15, group="B")])
        opt = b.build_echarts_option(spec)
        assert len(opt["series"]) == 2

    def test_axis_labels(self):
        b = LineChartBuilder()
        spec = ChartSpec(title="L", chart_type="line", x_axis_label="Month", y_axis_label="$",
                         data=[ChartDataPoint(name="Jan", value=100)])
        opt = b.build_echarts_option(spec)
        assert opt["xAxis"]["name"] == "Month"
        assert opt["yAxis"]["name"] == "$"


class TestBarChartBuilder:
    def test_basic(self):
        b = BarChartBuilder()
        spec = ChartSpec(title="R", chart_type="bar",
                         data=[ChartDataPoint(name="A", value=30)])
        opt = b.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "bar"


class TestPieChartBuilder:
    def test_basic(self):
        b = PieChartBuilder()
        spec = ChartSpec(title="S", chart_type="pie",
                         data=[ChartDataPoint(name="A", value=30), ChartDataPoint(name="B", value=70)])
        opt = b.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "pie"
        assert len(opt["series"][0]["data"]) == 2
        assert opt["series"][0]["data"][0]["value"] == 30

    def test_has_radius(self):
        b = PieChartBuilder()
        spec = ChartSpec(title="P", chart_type="pie", data=[ChartDataPoint(name="X", value=100)])
        opt = b.build_echarts_option(spec)
        assert "radius" in opt["series"][0]


class TestScatterChartBuilder:
    def test_basic(self):
        b = ScatterChartBuilder()
        spec = ChartSpec(title="C", chart_type="scatter",
                         data=[ChartDataPoint(name="P1", value=10), ChartDataPoint(name="P2", value=20)])
        opt = b.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "scatter"

    def test_multi_group(self):
        b = ScatterChartBuilder()
        spec = ChartSpec(title="G", chart_type="scatter",
                         data=[ChartDataPoint(name="X", value=10, group="G1"),
                               ChartDataPoint(name="Y", value=20, group="G2")])
        opt = b.build_echarts_option(spec)
        assert len(opt["series"]) == 2


class TestAreaChartBuilder:
    def test_basic(self):
        b = AreaChartBuilder()
        spec = ChartSpec(title="A", chart_type="area", data=[ChartDataPoint(name="Q1", value=100)])
        opt = b.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "line"
        assert "areaStyle" in opt["series"][0]


class TestRadarChartBuilder:
    def test_basic(self):
        b = RadarChartBuilder()
        spec = ChartSpec(title="R", chart_type="radar",
                         data=[ChartDataPoint(name="Speed", value=80),
                               ChartDataPoint(name="Power", value=60)])
        opt = b.build_echarts_option(spec)
        assert opt["series"][0]["type"] == "radar"
        assert len(opt["radar"]["indicator"]) == 2

    def test_multi_series(self):
        b = RadarChartBuilder()
        spec = ChartSpec(title="MR", chart_type="radar",
                         data=[ChartDataPoint(name="A", value=80, group="T1"),
                               ChartDataPoint(name="A", value=70, group="T2")])
        opt = b.build_echarts_option(spec)
        assert len(opt["series"]) == 2


class TestAllChartTypes:
    def test_all_six_types(self):
        builders = {"line": LineChartBuilder(), "bar": BarChartBuilder(),
                    "pie": PieChartBuilder(), "scatter": ScatterChartBuilder(),
                    "area": AreaChartBuilder(), "radar": RadarChartBuilder()}
        data = [ChartDataPoint(name="X", value=10), ChartDataPoint(name="Y", value=20)]
        for ct, builder in builders.items():
            spec = ChartSpec(title=ct, chart_type=ct, data=data)
            opt = builder.build_echarts_option(spec)
            assert "series" in opt, f"{ct}: missing series"
            assert len(opt["series"]) >= 1, f"{ct}: empty series"
