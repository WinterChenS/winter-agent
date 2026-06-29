"""Tests for ChartResult — structured chart output with summary computation."""
from __future__ import annotations

import json
import math

import pytest

from chart.chart_result import ChartResult


class TestChartResult:
    def test_create_minimal(self):
        r = ChartResult(image_path="/tmp/test.png", metadata={}, summary="", stdout="")
        assert r.image_path == "/tmp/test.png"
        assert r.metadata == {}
        assert r.summary == ""
        assert r.stdout == ""

    def test_create_full(self):
        r = ChartResult(
            image_path="/tmp/test.png",
            metadata={"title": "Test", "chart_type": "bar"},
            summary="Max: 100, Min: 10, Avg: 55.0",
            stdout="[INFO] rendering complete",
        )
        assert r.metadata["title"] == "Test"
        assert r.summary.startswith("Max:")

    def test_to_dict(self):
        r = ChartResult(
            image_path="/tmp/test.png",
            metadata={"title": "T"},
            summary="sum",
            stdout="",
        )
        d = r.to_dict()
        assert d["image_path"] == "/tmp/test.png"
        assert d["metadata"]["title"] == "T"
        assert d["summary"] == "sum"

    def test_to_dict_json_serializable(self):
        r = ChartResult(
            image_path="/tmp/test.png",
            metadata={"title": "T"},
            summary="Max: 100",
            stdout="",
        )
        json_str = json.dumps(r.to_dict(), ensure_ascii=False)
        assert isinstance(json_str, str)


class TestComputeSummary:
    def test_basic_stats(self):
        summary = ChartResult.compute_summary([10, 20, 30, 40, 100])
        assert "Max: 100.0" in summary
        assert "Min: 10.0" in summary
        assert "Avg: 40.0" in summary

    def test_ascending_trend(self):
        summary = ChartResult.compute_summary([1, 2, 3, 4, 5])
        assert "trend: ↑" in summary or "上升" in summary

    def test_descending_trend(self):
        summary = ChartResult.compute_summary([5, 4, 3, 2, 1])
        assert "trend: ↓" in summary or "下降" in summary

    def test_empty_list(self):
        summary = ChartResult.compute_summary([])
        assert "No data" in summary or summary == ""

    def test_single_value(self):
        summary = ChartResult.compute_summary([42])
        assert "Max" in summary
        assert "42" in summary

    def test_growth_rate_positive(self):
        summary = ChartResult.compute_summary([100, 150])
        assert "growth" in summary.lower()
        assert "50.0%" in summary
