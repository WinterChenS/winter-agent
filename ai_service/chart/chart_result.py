"""Structured chart output types.

ChartResult is the return type of all renderers. ChartMetadata carries
structured information for downstream consumers (SSE, prompts, reports).
SeriesInfo provides per-series color metadata so LLM composers can
reference colors by name.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SeriesInfo:
    """Metadata for a single data series in a chart."""
    name: str
    color: str       # hex, e.g. "#2F80ED"
    color_name: str  # Chinese, e.g. "蓝色"


@dataclass
class DataFacts:
    """Auto-extracted data range facts from the rendered figure.

    Populated by the renderer from axes data limits — NOT from LLM.
    These are authoritative facts the composer MUST use for descriptions.
    """
    x_min: str = ""
    x_max: str = ""
    y_min: str = ""
    y_max: str = ""
    data_points: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "x_min": self.x_min,
            "x_max": self.x_max,
            "y_min": self.y_min,
            "y_max": self.y_max,
            "data_points": self.data_points,
        }

    def to_range_hint(self) -> str:
        """Generate a factual range description."""
        parts = []
        if self.x_min and self.x_max:
            parts.append(f"X轴范围: {self.x_min} 至 {self.x_max}")
        if self.y_min and self.y_max:
            parts.append(f"Y轴范围: {self.y_min} 至 {self.y_max}")
        if self.data_points:
            parts.append(f"数据点数: {self.data_points}")
        return "；".join(parts) if parts else ""


@dataclass
class ChartMetadata:
    """Structured metadata extracted from or declared by a chart.

    Can be populated from:
      L1: __chart_metadata__ dict (declared by generated code)
      L2: figure state fallback (axis labels, legend titles, etc.)
    """
    title: str
    chart_type: str
    xlabel: str = ""
    ylabel: str = ""
    series: list[SeriesInfo] = field(default_factory=list)
    data_facts: DataFacts = field(default_factory=DataFacts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        result = {
            "title": self.title,
            "chart_type": self.chart_type,
            "xlabel": self.xlabel,
            "ylabel": self.ylabel,
            "series": [
                {"name": s.name, "color": s.color, "color_name": s.color_name}
                for s in self.series
            ],
        }
        if self.data_facts.data_points > 0:
            result["data_facts"] = self.data_facts.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChartMetadata:
        """Deserialize from a dict (e.g., loaded from metadata.json)."""
        series_list = [
            SeriesInfo(name=s["name"], color=s["color"], color_name=s["color_name"])
            for s in data.get("series", [])
        ]
        facts_raw = data.get("data_facts", {})
        facts = DataFacts(
            x_min=facts_raw.get("x_min", ""),
            x_max=facts_raw.get("x_max", ""),
            y_min=facts_raw.get("y_min", ""),
            y_max=facts_raw.get("y_max", ""),
            data_points=facts_raw.get("data_points", 0),
        )
        return cls(
            title=data.get("title", ""),
            chart_type=data.get("chart_type", ""),
            xlabel=data.get("xlabel", ""),
            ylabel=data.get("ylabel", ""),
            series=series_list,
            data_facts=facts,
        )

    def to_markdown_hint(self) -> str:
        """Generate an LLM-friendly markdown snippet describing the chart.

        Includes authoritative data_facts extracted from figure state.
        The LLM composer MUST use these facts, NOT invent date ranges.
        """
        lines: list[str] = []
        lines.append(f"图表: {self.title} ({self.chart_type})")
        for s in self.series:
            lines.append(f" - {s.name}: {s.color_name} ({s.color})")
        range_hint = self.data_facts.to_range_hint()
        if range_hint:
            lines.append(f"数据事实（来源：图表自动提取，请使用此数据而非猜测）: {range_hint}")
        return "\n".join(lines)


@dataclass
class ChartResult:
    """Complete output of a chart rendering operation."""
    image_path: str
    metadata: ChartMetadata
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "image_path": self.image_path,
            "metadata": self.metadata.to_dict(),
            "summary": self.summary,
        }
