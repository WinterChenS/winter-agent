"""Abstract chart renderer — extensibility point for matplotlib/seaborn/plotly."""
from __future__ import annotations

from abc import ABC, abstractmethod

from chart.chart_result import ChartResult


class AbstractChartRenderer(ABC):
    """Base class for chart rendering engines. Extend for new backends."""

    @abstractmethod
    def render(self, code: str, output_path: str) -> ChartResult:
        """Execute rendering code, saving chart to output_path. Returns ChartResult."""
        ...
