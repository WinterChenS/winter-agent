"""Tests for MatplotlibRenderer v2 — ChartResult return, metadata extraction, font validation."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from chart.chart_result import ChartResult, ChartMetadata, SeriesInfo
from chart.renderers.matplotlib_renderer import MatplotlibRenderer


@pytest.fixture
def renderer():
    return MatplotlibRenderer()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


SIMPLE_CHART_CODE = """\
import matplotlib.pyplot as plt
import numpy as np

x = np.arange(1, 6)
y = np.array([10, 20, 15, 25, 30])

__chart_metadata__ = {
    "chart_type": "line",
    "title": "Test Chart",
    "series": [
        {"name": "Series A", "color": "#2F80ED", "color_name": "蓝色"},
    ],
    "summary": "Test chart summary",
}

fig, ax = plt.subplots()
ax.plot(x, y, color="#2F80ED", label="Series A")
ax.set_title("Test Chart")
ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.legend()
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
"""


class TestRenderReturnsChartResult:
    def test_render_returns_chart_result(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(SIMPLE_CHART_CODE, output_path)
        assert isinstance(result, ChartResult)
        assert result.image_path == output_path

    def test_render_metadata_from_chart_metadata(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(SIMPLE_CHART_CODE, output_path)
        assert result.metadata.title == "Test Chart"
        assert result.metadata.chart_type == "line"
        assert result.metadata.xlabel == "X"
        assert result.metadata.ylabel == "Y"
        assert len(result.metadata.series) == 1
        assert result.metadata.series[0].name == "Series A"
        assert result.metadata.series[0].color == "#2F80ED"
        assert result.metadata.series[0].color_name == "蓝色"

    def test_render_summary(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(SIMPLE_CHART_CODE, output_path)
        assert result.summary == "Test chart summary"

    def test_render_metadata_json_file_created(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        renderer.render(SIMPLE_CHART_CODE, output_path)
        json_path = output_path.replace(".png", "_metadata.json")
        assert os.path.isfile(json_path)
        with open(json_path) as f:
            data = json.load(f)
        assert data["title"] == "Test Chart"
        assert data["chart_type"] == "line"


class TestRenderWithoutMetadataDecl:
    """When __chart_metadata__ is not set, fall back to figure state (L2)."""

    CODE_NO_METADATA = """\
import matplotlib.pyplot as plt
import numpy as np

fig, ax = plt.subplots()
ax.plot([1,2,3], [4,5,6], label="My Series")
ax.set_title("Fallback Title")
ax.set_xlabel("X Axis")
ax.set_ylabel("Y Axis")
ax.legend()
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
"""

    def test_l2_fallback_extracts_title_from_axes(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(self.CODE_NO_METADATA, output_path)
        assert result.metadata.title == "Fallback Title"
        assert result.metadata.xlabel == "X Axis"
        assert result.metadata.ylabel == "Y Axis"

    def test_l2_fallback_chart_type_is_unknown(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(self.CODE_NO_METADATA, output_path)
        assert result.metadata.chart_type == "unknown"

    def test_l2_fallback_series_from_legend(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(self.CODE_NO_METADATA, output_path)
        # Series should be extracted from legend handles
        if result.metadata.series:
            assert result.metadata.series[0].name == "My Series"


class TestFontInjection:
    def test_cn_font_injected_into_context(self, renderer, temp_dir):
        """cn_font should be available in exec context."""
        code = """\
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.set_title("Test", fontproperties=cn_font)
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
"""
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(code, output_path)
        assert result.image_path == output_path
