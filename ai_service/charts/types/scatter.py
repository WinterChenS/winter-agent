from typing import Any

from charts import BaseChartBuilder
from domain.chart_spec import ChartSpec


class ScatterChartBuilder(BaseChartBuilder):
    chart_type = "scatter"

    def build_echarts_option(self, spec: ChartSpec) -> dict[str, Any]:
        groups: dict[str, list[list[float]]] = {}
        for i, d in enumerate(spec.data):
            g = d.group or "value"
            if g not in groups:
                groups[g] = []
            groups[g].append([float(i), d.value])

        series = [
            {"name": g, "type": "scatter", "data": vals}
            for g, vals in groups.items()
        ]
        return {
            "title": {"text": spec.title or ""},
            "xAxis": {"type": "value", "name": spec.x_axis_label or ""},
            "yAxis": {"type": "value", "name": spec.y_axis_label or ""},
            "series": series,
        }
