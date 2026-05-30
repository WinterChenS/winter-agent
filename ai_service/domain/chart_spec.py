from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

ChartType = Literal["line", "bar", "pie", "scatter", "area", "radar"]


@dataclass(slots=True)
class ChartDataPoint:
    name: str
    value: float | int
    group: str = ""


@dataclass(slots=True)
class ChartSpec:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    chart_type: ChartType = "bar"
    description: str = ""
    x_axis_label: str = ""
    y_axis_label: str = ""
    data: list[ChartDataPoint] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "chartType": self.chart_type,
            "description": self.description,
            "xAxisLabel": self.x_axis_label,
            "yAxisLabel": self.y_axis_label,
            "data": [
                {"name": d.name, "value": d.value, "group": d.group}
                for d in self.data
            ],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ChartSpec":
        return cls(
            id=str(d.get("id", uuid.uuid4().hex[:12])),
            title=str(d.get("title", "")),
            chart_type=str(d.get("chartType", "bar")),
            description=str(d.get("description", "")),
            x_axis_label=str(d.get("xAxisLabel", "")),
            y_axis_label=str(d.get("yAxisLabel", "")),
            data=[
                ChartDataPoint(
                    name=str(item.get("name", "")),
                    value=float(item.get("value", 0)),
                    group=str(item.get("group", "")),
                )
                for item in d.get("data", [])
            ],
        )


CHART_SPEC_JSON_SCHEMA = {
    "type": "object",
    "required": ["title", "chartType", "data"],
    "properties": {
        "title": {"type": "string", "description": "Chart title"},
        "chartType": {
            "type": "string",
            "enum": ["line", "bar", "pie", "scatter", "area", "radar"],
            "description": "Chart type",
        },
        "description": {"type": "string", "description": "Brief description of the chart"},
        "xAxisLabel": {"type": "string", "description": "X-axis label"},
        "yAxisLabel": {"type": "string", "description": "Y-axis label"},
        "data": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "value"],
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "number"},
                    "group": {"type": "string"},
                },
            },
        },
    },
}
