"""Matplotlib chart renderer."""
from __future__ import annotations

from chart.chart_renderer import AbstractChartRenderer
from chart.chart_theme import ChartTheme


class MatplotlibRenderer(AbstractChartRenderer):
    """Render charts using matplotlib with enterprise theme."""

    def render(self, code: str, output_path: str) -> str:
        ChartTheme.initialize()

        import matplotlib.pyplot as plt
        plt.close("all")

        # Build execution context
        ctx = {
            "__output_path__": output_path,
            "plt": plt,
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
        if not __import__("os").path.exists(output_path):
            # Check if any figure was created
            if figs:
                figs[-1].savefig(output_path, dpi=200, bbox_inches="tight")
            else:
                # No figure at all — save a blank one
                fig, ax = plt.subplots(figsize=(16, 9))
                ax.text(0.5, 0.5, "No chart data", ha="center", va="center", fontsize=16)
                ax.set_axis_off()
                fig.savefig(output_path, dpi=200, bbox_inches="tight")
                plt.close(fig)

        plt.close("all")
        return output_path
