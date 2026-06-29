"""Structured chart output types.

ChartResult is the return type of all renderers. compute_summary() provides
programmatic text summaries (max/min/avg/trend/growth_rate) for the composer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ChartResult:
    """Complete output of a chart rendering operation.

    Fields:
        image_path: Absolute path to the generated PNG.
        metadata: Dict from ChartSpec.to_metadata() (or {} for legacy code).
        summary: Text summary from compute_summary().
        stdout: Captured stdout from rendering (if any).
    """
    image_path: str
    metadata: dict
    summary: str
    stdout: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_path": self.image_path,
            "metadata": self.metadata,
            "summary": self.summary,
        }

    @staticmethod
    def compute_summary(values: list[float], labels: list[str] | None = None) -> str:
        """Compute a programmatic text summary from numeric values.

        Includes max, min, avg, trend direction (linear regression slope),
        and growth rate (first to last value).

        Args:
            values: List of numeric values.
            labels: Optional per-value labels (not yet used).

        Returns:
            Text summary suitable for LLM consumption, or empty string if
            values is empty.
        """
        # Filter out None and non-numeric values
        clean = [float(v) for v in values if v is not None]
        if not clean:
            return ""

        n = len(clean)
        max_val = max(clean)
        min_val = min(clean)
        avg_val = sum(clean) / n

        parts = [f"Max: {max_val}", f"Min: {min_val}", f"Avg: {avg_val}"]

        if n >= 2:
            # Linear regression slope for trend
            x_mean = (n - 1) / 2.0
            y_mean = avg_val
            num = 0.0
            den = 0.0
            for i, v in enumerate(clean):
                dx = i - x_mean
                dy = v - y_mean
                num += dx * dy
                den += dx * dx
            slope = num / den if den != 0 else 0.0
            if slope > 0.01:
                parts.append("trend: ↑")
            elif slope < -0.01:
                parts.append("trend: ↓")
            else:
                parts.append("trend: →")

            # Growth rate (first to last)
            first = clean[0]
            last = clean[-1]
            if first != 0:
                growth = ((last - first) / abs(first)) * 100.0
                parts.append(f"growth: {growth:+.1f}%")

        return " | ".join(parts)
