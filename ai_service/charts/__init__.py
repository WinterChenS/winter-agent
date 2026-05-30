from abc import ABC, abstractmethod
from typing import Any

from domain.chart_spec import ChartSpec


class BaseChartBuilder(ABC):
    chart_type: str

    @abstractmethod
    def build_echarts_option(self, spec: ChartSpec) -> dict[str, Any]:
        """Build ECharts option dict from ChartSpec."""


class ChartTypeRegistry:
    def __init__(self) -> None:
        self._builders: dict[str, BaseChartBuilder] = {}

    def register(self, builder: BaseChartBuilder) -> None:
        self._builders[builder.chart_type] = builder

    def get(self, chart_type: str) -> BaseChartBuilder | None:
        return self._builders.get(chart_type)

    def list_types(self) -> list[str]:
        return list(self._builders.keys())

    def build_echarts_option(self, spec: ChartSpec) -> dict[str, Any]:
        builder = self._builders.get(spec.chart_type)
        if builder is None:
            builder = self._builders.get("bar")
        if builder is None:
            return _fallback_option(spec)
        return builder.build_echarts_option(spec)


def _fallback_option(spec: ChartSpec) -> dict[str, Any]:
    names = [d.name for d in spec.data]
    values = [d.value for d in spec.data]
    return {
        "title": {"text": spec.title or ""},
        "xAxis": {"type": "category", "data": names},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar", "data": values}],
    }


chart_registry = ChartTypeRegistry()
