"""Tests for MatplotlibRenderer -- render_from_spec, backward-compatible render, metadata."""
from __future__ import annotations

import json
import os
import tempfile

import pytest
import matplotlib.pyplot as plt

from chart.chart_result import ChartResult
from chart.chart_spec import ChartSpec, SeriesSpec, SliceSpec, PointSpec
from chart.renderers.matplotlib_renderer import MatplotlibRenderer


@pytest.fixture
def renderer():
    return MatplotlibRenderer()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestRenderFromSpec:
    def test_render_bar(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Test Bar",
            chart_type="bar",
            xlabel="X",
            ylabel="Y",
            series=[SeriesSpec(name="S1", color="#2F80ED", color_name="蓝色", values=[10, 20, 30])],
        )
        output = os.path.join(temp_dir, "bar.png")
        result = renderer.render_from_spec(spec, output)
        assert isinstance(result, ChartResult)
        assert result.image_path == output
        assert os.path.isfile(output)

    def test_value_label_preserves_meaningful_decimals(self, renderer):
        assert renderer._format_value_label(8.5) == "8.5"
        assert renderer._format_value_label(6.25) == "6.25"
        assert renderer._format_value_label(4.0) == "4"

    def test_dense_date_labels_are_thinned_and_rotated(self, renderer):
        fig, ax = plt.subplots()
        labels = [f"2025-02-{day:02d}" for day in range(1, 21)]
        ax.set_xticks(range(len(labels)))
        renderer._apply_x_axis_label_policy(ax, labels, None)
        assert len(ax.get_xticks()) < len(labels)
        assert ax.get_xticklabels()[0].get_rotation() == 35
        assert ax.get_xticklabels()[0].get_ha() == "right"
        plt.close(fig)

    def test_short_sparse_labels_stay_horizontal(self, renderer):
        fig, ax = plt.subplots()
        labels = ["科技", "消费", "金融"]
        ax.set_xticks(range(len(labels)))
        renderer._apply_x_axis_label_policy(ax, labels, None)
        assert len(ax.get_xticks()) == len(labels)
        assert ax.get_xticklabels()[0].get_rotation() == 0
        plt.close(fig)

    def test_render_line(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Test Line",
            chart_type="line",
            series=[SeriesSpec(name="S1", color="#27AE60", color_name="绿色", values=[1, 2, 3])],
        )
        output = os.path.join(temp_dir, "line.png")
        result = renderer.render_from_spec(spec, output)
        assert os.path.isfile(output)
        assert result.metadata["title"] == "Test Line"
        assert result.metadata["chart_type"] == "line"

    def test_render_pie(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Test Pie",
            chart_type="pie",
            slices=[SliceSpec("A", 30, "#EB5757", "红色"), SliceSpec("B", 70, "#2F80ED", "蓝色")],
        )
        output = os.path.join(temp_dir, "pie.png")
        result = renderer.render_from_spec(spec, output)
        assert os.path.isfile(output)

    def test_render_scatter(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Test Scatter",
            chart_type="scatter",
            points=[PointSpec(1, 2), PointSpec(3, 4), PointSpec(5, 6)],
        )
        output = os.path.join(temp_dir, "scatter.png")
        result = renderer.render_from_spec(spec, output)
        assert os.path.isfile(output)

    def test_metadata_json_created(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Meta",
            chart_type="bar",
            series=[SeriesSpec("S", "#2F80ED", "蓝色", [1])],
        )
        output = os.path.join(temp_dir, "meta.png")
        renderer.render_from_spec(spec, output)
        json_path = output.replace(".png", "_metadata.json")
        assert os.path.isfile(json_path)
        with open(json_path) as f:
            data = json.load(f)
        assert data["title"] == "Meta"
        assert data["chart_type"] == "bar"

    def test_metadata_contains_summary(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Summary Test",
            chart_type="bar",
            series=[SeriesSpec("S", "#2F80ED", "蓝色", [10, 20, 30])],
        )
        output = os.path.join(temp_dir, "summary.png")
        result = renderer.render_from_spec(spec, output)
        assert "Max" in result.summary

    def test_metadata_json_includes_summary_key(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Meta Summary",
            chart_type="bar",
            series=[SeriesSpec("S", "#2F80ED", "蓝色", [10, 20, 30])],
        )
        output = os.path.join(temp_dir, "meta_summary.png")
        renderer.render_from_spec(spec, output)
        json_path = output.replace(".png", "_metadata.json")
        with open(json_path) as f:
            data = json.load(f)
        assert "_summary" in data, "metadata JSON must include _summary for sandbox tool"
        assert "Max" in data["_summary"]


class TestRenderBackwardCompat:
    CODE_NO_SPEC = """\
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot([1,2,3], [4,5,6], label="My Series")
ax.set_title("Legacy")
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
plt.close(fig)
"""

    def test_render_returns_chart_result(self, renderer, temp_dir):
        output = os.path.join(temp_dir, "legacy.png")
        result = renderer.render(self.CODE_NO_SPEC, output)
        assert isinstance(result, ChartResult)
        assert result.image_path == output

    def test_legacy_metadata_is_empty_dict(self, renderer, temp_dir):
        output = os.path.join(temp_dir, "legacy.png")
        result = renderer.render(self.CODE_NO_SPEC, output)
        assert result.metadata == {}

    def test_legacy_summary_is_empty(self, renderer, temp_dir):
        output = os.path.join(temp_dir, "legacy.png")
        result = renderer.render(self.CODE_NO_SPEC, output)
        assert result.summary == ""

    def test_cn_font_injected(self, renderer, temp_dir):
        code = """\
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.set_title("Test", fontproperties=cn_font)
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
plt.close(fig)
"""
        output = os.path.join(temp_dir, "font_test.png")
        result = renderer.render(code, output)
        assert result.image_path == output
