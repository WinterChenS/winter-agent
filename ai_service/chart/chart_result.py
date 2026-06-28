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
    y_axis: str = "left"  # "left" or "right" — which y-axis this series uses


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
                {"name": s.name, "color": s.color, "color_name": s.color_name, "y_axis": s.y_axis}
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
            SeriesInfo(name=s["name"], color=s["color"], color_name=s["color_name"],
                       y_axis=s.get("y_axis", "left"))
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
            axis_label = f"（{s.y_axis}轴）" if s.y_axis == "right" else ""
            lines.append(f" - {s.name}: {s.color_name} ({s.color}){axis_label}")
        range_hint = self.data_facts.to_range_hint()
        if range_hint:
            lines.append(f"数据事实（来源：图表自动提取，请使用此数据而非猜测）: {range_hint}")
        factual = self.to_factual_description()
        if factual:
            lines.append(f"")
            lines.append(f"【以下为程序自动生成的图表描述，你必须逐字引用，不得修改其中的数据事实】")
            lines.append(factual)
        return "\n".join(lines)

    def to_factual_description(self) -> str:
        """Generate a deterministic, programmatic chart description.

        This description is generated entirely from machine-extracted facts
        (data_facts, series, y_axis affiliations). No LLM is involved.
        The composer MUST quote this verbatim for chart descriptions.
        """
        chart_type_names = {
            "line": "折线图", "bar": "柱状图", "pie": "饼图",
            "scatter": "散点图", "area": "面积图", "radar": "雷达图",
            "hist": "直方图", "box": "箱线图",
        }
        type_cn = chart_type_names.get(self.chart_type, self.chart_type)

        parts = [f"该{type_cn}展示了{self.title}。"]

        if self.data_facts.data_points > 0:
            parts.append(f"共{self.data_facts.data_points}个数据点。")

        for s in self.series:
            axis_info = "右轴" if s.y_axis == "right" else "左轴"
            parts.append(f"{s.name}（{axis_info}，{s.color_name}）。")

        if self.data_facts.x_min and self.data_facts.x_max:
            parts.append(f"X轴范围为{self.data_facts.x_min}至{self.data_facts.x_max}。")
        if self.data_facts.y_min and self.data_facts.y_max:
            parts.append(f"Y轴范围为{self.data_facts.y_min}至{self.data_facts.y_max}。")

        return "".join(parts)


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
