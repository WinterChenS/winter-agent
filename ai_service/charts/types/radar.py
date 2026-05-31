from typing import Any

from charts import BaseChartBuilder
from domain.chart_spec import ChartSpec


class RadarChartBuilder(BaseChartBuilder):
    chart_type = "radar"

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

        indicators = [{"name": n, "max": max(groups[g][i] for g in groups) * 1.2} for i, n in enumerate(names)]
        series = [
            {"name": g, "type": "radar", "data": [{"value": vals, "name": g}]}
            for g, vals in groups.items()
        ]
        return {
            "title": {"text": spec.title or ""},
            "radar": {"indicator": indicators},
            "series": series,
        }
