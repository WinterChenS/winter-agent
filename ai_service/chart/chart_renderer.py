"""Abstract chart renderer — extensibility point for matplotlib/seaborn/plotly."""
from __future__ import annotations

from abc import ABC, abstractmethod

from chart.chart_result import ChartResult
from chart.chart_spec import ChartSpec


class AbstractChartRenderer(ABC):
    """Base class for chart rendering engines. Extend for new backends."""

    @abstractmethod
    def render(self, code: str, output_path: str) -> ChartResult:
        """Execute rendering code, saving chart to output_path. Returns ChartResult."""
        ...

    @abstractmethod
    def render_from_spec(self, spec: ChartSpec, output_path: str) -> ChartResult:
        """Render from a ChartSpec directly (new, preferred path). Returns ChartResult."""
        ...
