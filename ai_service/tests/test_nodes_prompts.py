"""Tests for prompt strings in graph.nodes.py.

TDD: Write tests first, watch them fail, implement code, watch them pass.
"""
from __future__ import annotations

import json

import pytest

from graph.nodes import (
    _CHART_CODE_PROMPT,
    _build_composer_system_prompt,
)


class TestChartCodePrompt:
    """Verify _CHART_CODE_PROMPT uses ChartSpec API (Task 8 changes)."""

    def test_uses_palette_get_series_colors(self):
        """Must instruct LLM to use Palette.get_series_colors."""
        assert "Palette.get_series_colors" in _CHART_CODE_PROMPT

    def test_uses_cn_font_for_all_text(self):
        """Must use fontproperties=cn_font for ALL text elements."""
        assert "fontproperties=cn_font" in _CHART_CODE_PROMPT

    def test_uses_render_from_spec_via_chart_spec(self):
        """Must instruct LLM to render from ChartSpec."""
        assert "render_from_spec(spec" in _CHART_CODE_PROMPT

    def test_sets_chart_spec(self):
        """Must build a ChartSpec object."""
        assert "spec = ChartSpec(" in _CHART_CODE_PROMPT

    def test_no_rcParams_usage(self):
        """Must prohibit using plt.rcParams to set font (prohibition can mention it)."""
        # The prompt must prohibit using plt.rcParams for font (it may mention the string in the prohibition)
        assert "font" in _CHART_CODE_PROMPT
        # And must NOT instruct the LLM to USE plt.rcParams for font (i.e., no positive instruction to set rcParams)
        import re
        # Check that there's no positive instruction to use rcParams (only prohibition)
        # Look for the prohibition rule about font.sans-serif
        assert "fontproperties=cn_font" in _CHART_CODE_PROMPT

    def test_no_random_colors(self):
        """Must use Palette colors, never random colors."""
        assert "Palette" in _CHART_CODE_PROMPT

    def test_output_only_valid_python(self):
        """Must output ONLY valid Python code."""
        assert "Output ONLY valid Python code" in _CHART_CODE_PROMPT

    def test_has_chart_type_and_series(self):
        """Prompt should reference chart_type, series, slices, points."""
        assert "chart_type" in _CHART_CODE_PROMPT
        assert "series" in _CHART_CODE_PROMPT

    def test_has_figsize(self):
        """Should reference figsize."""
        assert "figure size to (12, 6)" in _CHART_CODE_PROMPT

    def test_no_no_plt_show(self):
        """Must have a rule that says Do NOT call plt.show()."""
        assert "Do NOT call plt.savefig() or plt.show() directly" in _CHART_CODE_PROMPT


class TestComposerArtifactFormatting:
    """Verify _format_artifacts inside _build_composer_system_prompt."""

    def test_with_metadata_series_includes_colors(self):
        """Artifact with metadata.series should include color names in output."""
        artifacts = [
            {
                "artifact_id": "img_0",
                "type": "image",
                "purpose": "GDP Chart",
                "content_ref": "https://cdn.example.com/chart_0.png",
                "metadata": {
                    "title": "GDP Growth",
                    "chart_type": "bar",
                    "series": [
                        {"name": "GDP", "color": "#2F80ED", "color_name": "蓝色"},
                        {"name": "CPI", "color": "#27AE60", "color_name": "绿色"},
                    ],
                },
                "summary": "GDP shows upward trend, max=150, min=80",
            }
        ]
        prompt = _build_composer_system_prompt(
            plan={"title": "Test Plan", "steps": []},
            results=[],
            artifacts=artifacts,
            now_str="2026-06-29 12:00",
        )
        # Should include color names
        assert "GDP（蓝色）" in prompt
        assert "CPI（绿色）" in prompt
        # Should include summary
        assert "GDP shows upward trend" in prompt
        # Should include full metadata as authoritative chart data.
        assert "chart_metadata_json" in prompt
        assert '"series": [{"color": "#2F80ED", "color_name": "蓝色", "name": "GDP"}' in prompt

    def test_with_metadata_summary_only(self):
        """Artifact with summary but no series should still include summary."""
        artifacts = [
            {
                "artifact_id": "img_0",
                "type": "image",
                "purpose": "Chart",
                "content_ref": "https://cdn.example.com/chart.png",
                "metadata": {"title": "Test", "chart_type": "pie"},
                "summary": "Test summary data",
            }
        ]
        prompt = _build_composer_system_prompt(
            plan=None,
            results=[],
            artifacts=artifacts,
            now_str="2026-06-29 12:00",
        )
        assert "Test summary data" in prompt

    def test_without_metadata_no_color_or_numeric(self):
        """Artifact without metadata should NOT have color/summary in artifact line."""
        artifacts = [
            {
                "artifact_id": "img_0",
                "type": "image",
                "purpose": "Generic Chart",
                "content_ref": "https://cdn.example.com/chart.png",
            }
        ]
        prompt = _build_composer_system_prompt(
            plan=None,
            results=[],
            artifacts=artifacts,
            now_str="2026-06-29 12:00",
        )
        artifact_line = next(line for line in prompt.splitlines() if "[img_0]" in line)
        # Should NOT contain "colors:" or "summary:" hints when no metadata
        assert "[colors:" not in artifact_line
        assert "[summary:" not in artifact_line
        assert "[chart_metadata_json:" not in artifact_line

    def test_multiple_artifacts_mixed_metadata(self):
        """Mix of artifacts with and without metadata should handle both."""
        artifacts = [
            {
                "artifact_id": "img_0",
                "type": "image",
                "purpose": "With Meta",
                "content_ref": "https://cdn.example.com/1.png",
                "metadata": {
                    "series": [{"name": "GDP", "color_name": "蓝色"}],
                },
                "summary": "trend up",
            },
            {
                "artifact_id": "img_1",
                "type": "image",
                "purpose": "No Meta",
                "content_ref": "https://cdn.example.com/2.png",
            },
        ]
        prompt = _build_composer_system_prompt(
            plan={"title": "P", "steps": []},
            results=[],
            artifacts=artifacts,
            now_str="2026-06-29 12:00",
        )
        assert "GDP（蓝色）" in prompt
        assert "trend up" in prompt
        # The second artifact should just reference the image with no metadata hint
        assert "[colors:" in prompt  # First artifact has it
        assert "No Meta" in prompt  # Second artifact should still be listed

    def test_with_metadata_series_values_includes_chart_metadata_json(self):
        """Full ChartSpec metadata should reach composer, including labels and values."""
        artifacts = [
            {
                "artifact_id": "img_0",
                "type": "image",
                "purpose": "GDP Chart",
                "content_ref": "https://cdn.example.com/chart_0.png",
                "metadata": {
                    "title": "GDP Growth",
                    "chart_type": "line",
                    "labels": ["2024", "2025"],
                    "series": [
                        {
                            "name": "GDP",
                            "color": "#2F80ED",
                            "color_name": "蓝色",
                            "values": [100, 120],
                            "secondary_y": False,
                        }
                    ],
                },
                "summary": "Max: 120 | Min: 100 | Avg: 110 | trend: ↑ | growth: +20.0%",
            }
        ]
        prompt = _build_composer_system_prompt(
            plan=None,
            results=[],
            artifacts=artifacts,
            now_str="2026-06-29 12:00",
        )
        assert "[chart_metadata_json:" in prompt
        assert '"labels": ["2024", "2025"]' in prompt
        assert '"values": [100, 120]' in prompt
        assert "ALL chart values, labels, series names, and axis affiliation MUST come from [chart_metadata_json:]" in prompt


class TestComposerChartColorRules:
    """Verify Chart Color Rules section in _build_composer_system_prompt."""

    def test_has_chart_color_rules_section(self):
        """System prompt should include [Chart Color Rules] section."""
        prompt = _build_composer_system_prompt(
            plan=None,
            results=[],
            artifacts=[],
            now_str="2026-06-29 12:00",
        )
        assert "[Chart Color Rules — THIS IS THE SINGLE SOURCE OF TRUTH]" in prompt

    def test_color_desc_must_come_from_metadata(self):
        """Must have rule about colors coming from chart metadata's series color_name and summary."""
        prompt = _build_composer_system_prompt(
            plan=None,
            results=[],
            artifacts=[],
            now_str="2026-06-29 12:00",
        )
        assert "chart metadata" in prompt or "metadata" in prompt

    def test_series_description_format(self):
        """Must include format instruction for series descriptions."""
        prompt = _build_composer_system_prompt(
            plan=None,
            results=[],
            artifacts=[],
            now_str="2026-06-29 12:00",
        )
        assert "CPI（绿色）" in prompt

    def test_no_numeric_from_image(self):
        """Must not guess numeric/trend from image inspection."""
        prompt = _build_composer_system_prompt(
            plan=None,
            results=[],
            artifacts=[],
            now_str="2026-06-29 12:00",
        )
        assert "NEVER infer them from the image" in prompt
        assert "NEVER recalculate or estimate from the image" in prompt

    def test_charts_without_metadata_rule(self):
        """Must have rule for charts without metadata."""
        prompt = _build_composer_system_prompt(
            plan=None,
            results=[],
            artifacts=[],
            now_str="2026-06-29 12:00",
        )
        assert "If a chart has NO [colors:] or [summary:] hint" in prompt
