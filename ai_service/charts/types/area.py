from typing import Any

from charts import BaseChartBuilder
from domain.chart_spec import ChartSpec


class AreaChartBuilder(BaseChartBuilder):
    chart_type = "area"

    def build_echarts_option(self, spec: ChartSpec) -> dict[str, Any]:
        groups: dict[str, list[float]] = {}
        names: list[str] = []
        seen = set()
        for d in spec.data:
            if d.name not in seen:
                names.append(d.name)
                seen.add(d.name)
            g = d.group or "value"
            if g not in groups:
                groups[g] = []
            groups[g].append(d.value)

        series = [
            {"name": g, "type": "line", "data": vals, "areaStyle": {}}
            for g, vals in groups.items()
        ]
        return {
            "title": {"text": spec.title or ""},
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": names, "name": spec.x_axis_label or ""},
            "yAxis": {"type": "value", "name": spec.y_axis_label or ""},
            "series": series,
        }
