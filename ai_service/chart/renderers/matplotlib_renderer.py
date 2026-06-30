"""Matplotlib chart renderer — returns ChartResult via render() or render_from_spec()."""
from __future__ import annotations

import json
import logging
import os
import math
import re

from chart.chart_renderer import AbstractChartRenderer
from chart.font_manager import FontManager
from chart.chart_result import ChartResult
from chart.chart_spec import ChartSpec
from chart.palette import Palette

logger = logging.getLogger(__name__)


class MatplotlibRenderer(AbstractChartRenderer):
    """Render charts using matplotlib with enterprise theme.

    Two rendering paths:
      - render_from_spec(spec, path): preferred. Renders from ChartSpec.
      - render(code, path): backward-compatible. Executes raw Python code.
    Both return ChartResult.
    """

    def render(self, code: str, output_path: str) -> ChartResult:
        """Execute rendering code, saving chart to output_path.

        Injects cn_font, Palette, and __chart_spec__ into the exec context.
        If __chart_spec__ is declared, routes to render_from_spec internally.
        Otherwise returns ChartResult with empty metadata (legacy path).
        """
        FontManager.initialize()

        import matplotlib.pyplot as plt
        plt.close("all")

        ctx = {
            "__output_path__": output_path,
            "plt": plt,
            "cn_font": FontManager.get_cn_font(),
            "Palette": Palette,
            "__chart_spec__": None,
        }

        exec(code, ctx)

        figs = [plt.figure(n) for n in plt.get_fignums()]
        for fig in figs:
            try:
                fig.tight_layout()
            except Exception:
                pass

        if not os.path.exists(output_path):
            if figs:
                figs[-1].savefig(output_path, dpi=200, bbox_inches="tight")
            else:
                fig, ax = plt.subplots(figsize=(16, 9))
                ax.text(0.5, 0.5, "No chart data", ha="center", va="center", fontsize=16)
                ax.set_axis_off()
                fig.savefig(output_path, dpi=200, bbox_inches="tight")
                plt.close(fig)

        # Check if __chart_spec__ was declared
        chart_spec = ctx.get("__chart_spec__")
        if chart_spec and isinstance(chart_spec, dict):
            # Reconstruct ChartSpec from dict and use render_from_spec
            spec = self._spec_from_dict(chart_spec)
            result = self.render_from_spec(spec, output_path)
            plt.close("all")
            return result

        # Legacy path: empty metadata
        plt.close("all")
        return ChartResult(
            image_path=output_path,
            metadata={},
            summary="",
            stdout="",
        )

    def render_from_spec(self, spec: ChartSpec, output_path: str) -> ChartResult:
        """Render from a ChartSpec directly.

        This is the preferred rendering path. It:
        1. Creates a matplotlib figure from the spec
        2. Renders the appropriate chart type
        3. Saves _metadata.json alongside the PNG
        4. Computes and returns a text summary
        """
        FontManager.initialize()
        cn_font = FontManager.get_cn_font()

        import matplotlib.pyplot as plt
        plt.close("all")

        fig, ax = plt.subplots(figsize=spec.figsize)

        match spec.chart_type:
            case "bar":
                self._render_bar(ax, spec, cn_font)
            case "line":
                self._render_line(ax, spec, cn_font)
            case "pie":
                self._render_pie(ax, spec, cn_font)
            case "scatter":
                self._render_scatter(ax, spec, cn_font)
            case "histogram":
                self._render_histogram(ax, spec, cn_font)
            case "heatmap":
                self._render_heatmap(ax, spec, cn_font)
            case _:
                raise ValueError(f"Unknown chart_type: {spec.chart_type}")

        ax.set_title(spec.title, fontproperties=cn_font)
        if spec.xlabel:
            ax.set_xlabel(spec.xlabel, fontproperties=cn_font)
        if spec.ylabel:
            ax.set_ylabel(spec.ylabel, fontproperties=cn_font)

        fig.tight_layout()
        fig.savefig(output_path, dpi=200, bbox_inches="tight")

        # Summary (compute before metadata so sandbox _summary extraction works)
        summary = ChartResult.compute_summary(spec.all_values(), spec.labels)

        # Metadata (include _summary for sandbox tool backward compatibility)
        metadata = spec.to_metadata()
        metadata["_summary"] = summary
        meta_path = output_path.replace(".png", "_metadata.json")
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("Failed to save metadata JSON: %s", exc)

        plt.close("all")
        return ChartResult(
            image_path=output_path,
            metadata=metadata,
            summary=summary,
            stdout="",
        )

    def _render_bar(self, ax, spec: ChartSpec, cn_font) -> None:
        n_series = len(spec.series)
        n_vals = len(spec.series[0].values) if spec.series else 0
        import numpy as np
        x = np.arange(n_vals)
        width = 0.8 / n_series
        for i, s in enumerate(spec.series):
            offset = (i - n_series / 2 + 0.5) * width
            bars = ax.bar(x + offset, s.values, width, label=s.name, color=s.color)
            for bar in bars:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        self._format_value_label(bar.get_height()), ha="center", va="bottom",
                        fontsize=9, fontproperties=cn_font)
        ax.set_xticks(x)
        if spec.labels:
            self._apply_x_axis_label_policy(ax, spec.labels, cn_font)
        ax.legend(prop=cn_font)

    def _format_value_label(self, value: float) -> str:
        """Format chart value labels without dropping meaningful decimals."""
        if float(value).is_integer():
            return f"{value:.0f}"
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _render_line(self, ax, spec: ChartSpec, cn_font) -> None:
        import numpy as np
        import matplotlib.pyplot as plt

        x = np.arange(len(spec.series[0].values)) if spec.series else []
        has_secondary = any(s.secondary_y for s in spec.series) if spec.series else False
        ax2 = ax.twinx() if has_secondary else None

        for s in spec.series:
            target = ax2 if s.secondary_y and ax2 else ax
            target.plot(x, s.values, marker="o", label=s.name, color=s.color, linewidth=2)

        if spec.labels:
            ax.set_xticks(x)
            self._apply_x_axis_label_policy(ax, spec.labels, cn_font)

        # Combine legends from both axes
        lines1, labels1 = ax.get_legend_handles_labels()
        if ax2:
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, prop=cn_font)
        else:
            ax.legend(prop=cn_font)

    def _render_pie(self, ax, spec: ChartSpec, cn_font) -> None:
        if not spec.slices:
            return
        labels = [s.label for s in spec.slices]
        sizes = [s.value for s in spec.slices]
        colors = [s.color for s in spec.slices]
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors, autopct="%1.1f%%",
            startangle=90, textprops={"fontproperties": cn_font},
        )
        for t in texts:
            t.set_fontproperties(cn_font)

    def _render_scatter(self, ax, spec: ChartSpec, cn_font) -> None:
        if not spec.points:
            return
        xs = [p.x for p in spec.points]
        ys = [p.y for p in spec.points]
        ax.scatter(xs, ys, c=Palette.PRIMARY.hex, s=60)
        for p in spec.points:
            if p.label:
                ax.annotate(p.label, (p.x, p.y), fontsize=9, fontproperties=cn_font)

    def _render_histogram(self, ax, spec: ChartSpec, cn_font) -> None:
        import numpy as np
        if spec.data and spec.data[0]:
            ax.hist(spec.data[0], bins="auto", color=Palette.PRIMARY.hex, edgecolor="white")

    def _render_heatmap(self, ax, spec: ChartSpec, cn_font) -> None:
        import matplotlib.pyplot as plt
        import numpy as np
        if not spec.data:
            return
        data = np.array(spec.data)
        im = ax.imshow(data, cmap="Blues", aspect="auto")
        plt.colorbar(im, ax=ax)
        if spec.labels:
            ax.set_xticks(range(len(spec.labels)))
            self._apply_x_axis_label_policy(ax, spec.labels, cn_font)

    def _apply_x_axis_label_policy(self, ax, labels: list[str], cn_font) -> None:
        """Avoid overlapping dense/long x-axis labels by thinning and rotating them."""
        if not labels:
            return

        labels = [str(label) for label in labels]
        count = len(labels)
        has_long_label = any(len(label) >= 8 for label in labels)
        looks_like_date = any(re.search(r"\d{4}[-/年]\d{1,2}", label) for label in labels)
        dense = count > 10 or (count > 6 and (has_long_label or looks_like_date))

        if dense:
            max_ticks = 8
            step = max(1, math.ceil(count / max_ticks))
            tick_positions = list(range(0, count, step))
            if tick_positions[-1] != count - 1:
                tick_positions.append(count - 1)
            ax.set_xticks(tick_positions)
            tick_labels = [labels[i] for i in tick_positions]
            ax.set_xticklabels(tick_labels, fontproperties=cn_font, rotation=35, ha="right")
        else:
            ax.set_xticklabels(labels, fontproperties=cn_font)

    def _spec_from_dict(self, d: dict) -> ChartSpec:
        """Reconstruct a ChartSpec from a dict (e.g., from __chart_spec__)."""
        from chart.chart_spec import SeriesSpec, SliceSpec, PointSpec

        series = None
        if "series" in d:
            series = [SeriesSpec(**s) for s in d["series"]]
        slices = None
        if "slices" in d:
            slices = [SliceSpec(**s) for s in d["slices"]]
        points = None
        if "points" in d:
            points = [PointSpec(**p) for p in d["points"]]

        return ChartSpec(
            title=d.get("title", ""),
            chart_type=d.get("chart_type", "bar"),
            xlabel=d.get("xlabel"),
            ylabel=d.get("ylabel"),
            figsize=tuple(d.get("figsize", (12, 6))),
            series=series,
            slices=slices,
            points=points,
            data=d.get("data"),
            labels=d.get("labels"),
        )
