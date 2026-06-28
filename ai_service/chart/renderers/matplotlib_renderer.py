"""Matplotlib chart renderer — returns ChartResult with structured metadata."""
from __future__ import annotations

import json
import logging
import os

from chart.chart_renderer import AbstractChartRenderer
from chart.font_manager import FontManager
from chart.chart_result import ChartResult, ChartMetadata, SeriesInfo
from chart.palette import Palette

logger = logging.getLogger(__name__)


class MatplotlibRenderer(AbstractChartRenderer):
    """Render charts using matplotlib with enterprise theme.

    Returns a ChartResult containing the image path and structured metadata
    extracted from either the __chart_metadata__ variable (declared in code)
    or the matplotlib figure state (fallback).
    """

    def render(self, code: str, output_path: str) -> ChartResult:
        FontManager.initialize()

        import matplotlib.pyplot as plt
        plt.close("all")

        # Build execution context with injected variables
        ctx = {
            "__output_path__": output_path,
            "plt": plt,
            "cn_font": FontManager.get_cn_font(),
            "Palette": Palette,
            "__chart_metadata__": None,
        }

        exec(code, ctx)

        # Ensure tight_layout for Chinese label overlap prevention
        figs = [plt.figure(n) for n in plt.get_fignums()]
        for fig in figs:
            try:
                fig.tight_layout()
            except Exception:
                pass

        # If code didn't savefig, do it now
        if not os.path.exists(output_path):
            if figs:
                figs[-1].savefig(output_path, dpi=200, bbox_inches="tight")
            else:
                fig, ax = plt.subplots(figsize=(16, 9))
                ax.text(0.5, 0.5, "No chart data", ha="center", va="center", fontsize=16)
                ax.set_axis_off()
                fig.savefig(output_path, dpi=200, bbox_inches="tight")
                plt.close(fig)

        # ── Metadata extraction ──
        metadata = self._extract_metadata(ctx, figs)

        # ── Summary ──
        summary = ctx.get("__chart_metadata__", {}) or {}
        summary_text = summary.get("summary", "") if isinstance(summary, dict) else ""

        # ── Font validation (best-effort, non-blocking) ──
        for fig in figs:
            try:
                warnings = FontManager.validate_figure_fonts(fig)
                for w in warnings:
                    logger.warning("Font compliance: %s", w)
            except Exception:
                pass

        # ── Save metadata JSON alongside PNG ──
        self._save_metadata(output_path, metadata)

        plt.close("all")

        return ChartResult(
            image_path=output_path,
            metadata=metadata,
            summary=summary_text,
        )

    def _extract_metadata(
        self,
        ctx: dict,
        figs: list,
    ) -> ChartMetadata:
        """Extract chart metadata, with two-level fallback.

        L1: __chart_metadata__ dict from exec context (declared by generated code).
        L2: matplotlib figure state (axis labels, legend, etc.).

        Returns:
            Populated ChartMetadata instance.
        """
        declared = ctx.get("__chart_metadata__")
        if declared and isinstance(declared, dict):
            return self._extract_l1(declared, figs)
        return self._extract_l2(figs)

    def _extract_l1(self, declared: dict, figs: list) -> ChartMetadata:
        """Build metadata from __chart_metadata__ dict (L1)."""
        series_list = []
        for s in declared.get("series", []):
            series_list.append(SeriesInfo(
                name=s.get("name", ""),
                color=s.get("color", ""),
                color_name=s.get("color_name", ""),
            ))

        metadata = ChartMetadata(
            title=str(declared.get("title", "")),
            chart_type=str(declared.get("chart_type", "")),
            series=series_list,
        )

        # L2 fallback for any L1 gaps
        if figs:
            self._l2_fill_gaps(metadata, figs[-1])

        return metadata

    def _extract_l2(self, figs: list) -> ChartMetadata:
        """Build metadata from matplotlib figure state (L2 fallback)."""
        metadata = ChartMetadata(
            title="",
            chart_type="unknown",
        )
        if figs:
            self._l2_fill_gaps(metadata, figs[-1])
        return metadata

    def _l2_fill_gaps(self, metadata: ChartMetadata, fig) -> None:
        """Fill missing metadata fields from figure state."""
        import matplotlib.pyplot as plt

        for ax in fig.get_axes():
            if not metadata.title:
                t = ax.get_title()
                if t:
                    metadata.title = t
            if not metadata.xlabel:
                xl = ax.get_xlabel()
                if xl:
                    metadata.xlabel = xl
            if not metadata.ylabel:
                yl = ax.get_ylabel()
                if yl:
                    metadata.ylabel = yl

        # Extract series from legend
        if not metadata.series:
            for ax in fig.get_axes():
                legend = ax.get_legend()
                if legend is None:
                    continue
                for handle, label in zip(legend.legend_handles or [],
                                          [t.get_text() for t in legend.get_texts()]):
                    color_hex = "#000000"
                    try:
                        if hasattr(handle, "get_color"):
                            c = handle.get_color()
                            if isinstance(c, tuple):
                                from matplotlib.colors import rgb2hex
                                color_hex = rgb2hex(c)
                            else:
                                color_hex = str(c)
                        elif hasattr(handle, "get_facecolor"):
                            c = handle.get_facecolor()
                            if isinstance(c, tuple):
                                from matplotlib.colors import rgb2hex
                                color_hex = rgb2hex(c)
                            else:
                                color_hex = str(c)
                    except Exception:
                        pass
                    metadata.series.append(SeriesInfo(
                        name=label,
                        color=color_hex,
                        color_name=Palette.get_color_name(color_hex),
                    ))

    def _save_metadata(self, output_path: str, metadata: ChartMetadata) -> None:
        """Save ChartMetadata as a JSON file alongside the PNG output."""
        json_path = output_path.replace(".png", "_metadata.json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info("Saved chart metadata to %s", json_path)
        except Exception as exc:
            logger.warning("Failed to save metadata JSON: %s", exc)
