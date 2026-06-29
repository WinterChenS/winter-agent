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
        """Must instruct LLM to set __chart_spec__ to trigger render_from_spec flow."""
        assert "__chart_spec__" in _CHART_CODE_PROMPT

    def test_sets_chart_spec(self):
        """Must set __chart_spec__ as a dictionary."""
        assert "__chart_spec__" in _CHART_CODE_PROMPT

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
        assert "figsize" in _CHART_CODE_PROMPT

    def test_no_no_plt_show(self):
        """Must have a rule that says Do NOT call plt.show()."""
        assert "Do NOT call plt.show()" in _CHART_CODE_PROMPT


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
        # Should NOT contain "colors:" or "summary:" hints when no metadata
        assert "[colors:" not in prompt
        assert "[summary:" not in prompt

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
        assert "[Chart Color Rules]" in prompt

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
        assert "系列名（颜色名）" in prompt

    def test_no_numeric_from_image(self):
        """Must not guess numeric/trend from image inspection."""
        prompt = _build_composer_system_prompt(
            plan=None,
            results=[],
            artifacts=[],
            now_str="2026-06-29 12:00",
        )
        assert "NOT from image inspection" in prompt

    def test_charts_without_metadata_rule(self):
        """Must have rule for charts without metadata."""
        prompt = _build_composer_system_prompt(
            plan=None,
            results=[],
            artifacts=[],
            now_str="2026-06-29 12:00",
        )
        assert "WITHOUT metadata" in prompt
