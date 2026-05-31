from __future__ import annotations

import logging
from domain.chart_spec import ChartSpec, ChartDataPoint

logger = logging.getLogger(__name__)

ALLOWED_CHART_TYPES: set[str] = {"line", "bar", "pie", "scatter", "area", "radar"}

MAX_DATA_POINTS = 20
MAX_TITLE_LEN = 200
MAX_DESC_LEN = 500
MAX_LABEL_LEN = 100


def _validate_chart_type(ct: str) -> str:
    ct = str(ct).strip().lower()
    return ct if ct in ALLOWED_CHART_TYPES else "bar"


def _validate_data_points(data: list) -> list[ChartDataPoint]:
    result = []
    for d in data[:MAX_DATA_POINTS]:
        if not isinstance(d, dict):
            continue
        name = str(d.get("name", "")).strip()
        if not name:
            continue
        try:
            value = float(d.get("value", 0))
        except (ValueError, TypeError):
            continue
        group = str(d.get("group", "")).strip()
        result.append(ChartDataPoint(name=name, value=value, group=group))
    return result


def validate_chart_specs(charts: list) -> list[dict]:
    """Validate and normalize chart specs from LLM output. Returns list of ChartSpec dicts."""
    valid = []
    for c in charts:
        if not isinstance(c, dict):
            continue
        try:
            spec = ChartSpec(
                id=int(c.get("id", len(valid))),
                title=str(c.get("title", ""))[:MAX_TITLE_LEN],
                chart_type=_validate_chart_type(c.get("chart_type", "bar")),
                description=str(c.get("description", ""))[:MAX_DESC_LEN],
                x_axis_label=str(c.get("x_axis_label", ""))[:MAX_LABEL_LEN],
                y_axis_label=str(c.get("y_axis_label", ""))[:MAX_LABEL_LEN],
                data=_validate_data_points(c.get("data", [])),
            )
            if spec.data:
                valid.append(spec.to_dict())
        except Exception as e:
            logger.warning("Chart validation failed for item: %s", e)
    return valid
