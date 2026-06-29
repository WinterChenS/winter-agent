"""ChartSpec -- typed specification for chart rendering (single source of truth).

This module defines the data classes used to describe a chart declaratively.
ChartSpec is the single source of truth: metadata, rendering parameters, and
data values all flow from a single ChartSpec instance.

Usage:
    spec = ChartSpec(
        title="Sales",
        chart_type="bar",
        series=[SeriesSpec(name="Q1", color="#2F80ED", color_name="", values=[100, 200])],
    )
    meta = spec.to_metadata()   # -> dict for metadata.json and prompts
    vals = spec.all_values()    # -> [100, 200] for summary computation
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from chart.palette import Palette


@dataclass
class SeriesSpec:
    """A single data series in a bar or line chart."""
    name: str
    color: str
    color_name: str
    values: list[float]


@dataclass
class SliceSpec:
    """A single slice in a pie chart."""
    label: str
    value: float
    color: str
    color_name: str


@dataclass
class PointSpec:
    """A single point in a scatter chart."""
    x: float
    y: float
    label: str | None = None


@dataclass
class ChartSpec:
    """Declarative chart specification -- the single source of truth.

    Fields:
        title: Chart title.
        chart_type: One of line/bar/pie/scatter/histogram/heatmap.
        xlabel: X-axis label (bar/line/scatter/histogram).
        ylabel: Y-axis label (bar/line/scatter/histogram).
        figsize: (width, height) in inches.
        series: Data series for bar/line charts.
        slices: Data slices for pie charts.
        points: Data points for scatter charts.
        data: Raw data matrix for histogram/heatmap.
        labels: Category labels for histogram/heatmap.
    """
    title: str
    chart_type: str
    xlabel: str | None = None
    ylabel: str | None = None
    figsize: tuple = (12, 6)
    series: list[SeriesSpec] | None = None
    slices: list[SliceSpec] | None = None
    points: list[PointSpec] | None = None
    data: list[list[float]] | None = None
    labels: list[str] | None = None

    def __post_init__(self):
        if self.series:
            for s in self.series:
                if not s.color_name:
                    s.color_name = Palette.get_color_name(s.color)

    def to_metadata(self) -> dict[str, Any]:
        """Serialize ChartSpec to a metadata dict for the JSON file and prompts."""
        meta: dict[str, Any] = {
            "title": self.title,
            "chart_type": self.chart_type,
            "xlabel": self.xlabel,
            "ylabel": self.ylabel,
            "figsize": list(self.figsize),
        }
        if self.series:
            meta["series"] = [
                {"name": s.name, "color": s.color, "color_name": s.color_name}
                for s in self.series
            ]
        if self.slices:
            meta["slices"] = [
                {"label": s.label, "value": s.value, "color": s.color, "color_name": s.color_name}
                for s in self.slices
            ]
        if self.labels:
            meta["labels"] = self.labels
        return meta

    def all_values(self) -> list[float]:
        """Collect all numeric values from the spec for summary computation."""
        values: list[float] = []
        if self.series:
            for s in self.series:
                values.extend(s.values)
        if self.slices:
            for s in self.slices:
                values.append(s.value)
        if self.points:
            for p in self.points:
                values.append(p.x)
                values.append(p.y)
        return values
