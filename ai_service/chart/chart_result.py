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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "title": self.title,
            "chart_type": self.chart_type,
            "xlabel": self.xlabel,
            "ylabel": self.ylabel,
            "series": [
                {"name": s.name, "color": s.color, "color_name": s.color_name}
                for s in self.series
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChartMetadata:
        """Deserialize from a dict (e.g., loaded from metadata.json)."""
        series_list = [
            SeriesInfo(name=s["name"], color=s["color"], color_name=s["color_name"])
            for s in data.get("series", [])
        ]
        return cls(
            title=data.get("title", ""),
            chart_type=data.get("chart_type", ""),
            xlabel=data.get("xlabel", ""),
            ylabel=data.get("ylabel", ""),
            series=series_list,
        )

    def to_markdown_hint(self) -> str:
        """Generate an LLM-friendly markdown snippet describing the chart.

        Example:
            图表: GDP增长率 (bar)
             - GDP: 蓝色 (#2F80ED)
             - CPI: 绿色 (#27AE60)
            摘要: GDP在2020-2024年间稳定增长
        """
        lines: list[str] = []
        lines.append(f"图表: {self.title} ({self.chart_type})")
        for s in self.series:
            lines.append(f" - {s.name}: {s.color_name} ({s.color})")
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
