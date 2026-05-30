from __future__ import annotations

import logging
from typing import Any, Mapping

from domain.chart_spec import ChartSpec, ChartDataPoint
from tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

CHART_TOOL_DESCRIPTION = (
    "Generate a chart visualization. Use this when you have numerical data ready to display. "
    "Call this tool AFTER you've collected data — it creates an interactive chart that the user will see immediately. "
    "You can call this tool multiple times in one turn for different charts at different points in your analysis."
)

CHART_TOOL_SCHEMA = {
    "type": "object",
    "required": ["chart_type", "data"],
    "properties": {
        "chart_type": {
            "type": "string",
            "enum": ["line", "bar", "pie", "scatter", "area", "radar"],
            "description": "Chart type to generate",
        },
        "title": {
            "type": "string",
            "description": "Chart title",
        },
        "description": {
            "type": "string",
            "description": "Brief description of what the chart shows",
        },
        "x_axis_label": {
            "type": "string",
            "description": "X-axis label (for line/bar/scatter)",
        },
        "y_axis_label": {
            "type": "string",
            "description": "Y-axis label (for line/bar/scatter)",
        },
        "data": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "value"],
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "number"},
                    "group": {"type": "string", "description": "For multi-series charts"},
                },
            },
        },
    },
}


class ChartTool(BaseTool):
    name = "generate_chart"
    description = CHART_TOOL_DESCRIPTION
    input_schema = CHART_TOOL_SCHEMA

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        try:
            chart_type = str(input_payload.get("chart_type", "bar"))
            title = str(input_payload.get("title", ""))
            description = str(input_payload.get("description", ""))
            x_axis_label = str(input_payload.get("x_axis_label", ""))
            y_axis_label = str(input_payload.get("y_axis_label", ""))
            raw_data = input_payload.get("data", [])

            if not isinstance(raw_data, list) or not raw_data:
                return ToolResult.failure("INVALID_DATA", "data must be a non-empty array", retryable=False)

            data_points = []
            for item in raw_data:
                if isinstance(item, dict):
                    data_points.append(ChartDataPoint(
                        name=str(item.get("name", "")),
                        value=float(item.get("value", 0)),
                        group=str(item.get("group", "")),
                    ))

            spec = ChartSpec(
                title=title,
                chart_type=chart_type,
                description=description,
                x_axis_label=x_axis_label,
                y_axis_label=y_axis_label,
                data=data_points,
            )

            return ToolResult.success(spec.to_dict())

        except Exception as exc:
            logger.exception("ChartTool execution failed")
            return ToolResult.failure("TOOL_ERROR", str(exc)[:200], retryable=False)
