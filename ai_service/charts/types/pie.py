from typing import Any

from charts import BaseChartBuilder
from domain.chart_spec import ChartSpec


class PieChartBuilder(BaseChartBuilder):
    chart_type = "pie"

    def build_echarts_option(self, spec: ChartSpec) -> dict[str, Any]:
        pie_data = [
            {"name": d.name, "value": d.value}
            for d in spec.data
        ]
        return {
            "title": {"text": spec.title or ""},
            "tooltip": {"trigger": "item"},
            "series": [{
                "type": "pie",
                "radius": "60%",
                "data": pie_data,
                "emphasis": {
                    "itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0,0,0,0.5)"}
                },
            }],
        }
