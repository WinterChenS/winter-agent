"""Enterprise chart theme — unified font, color, DPI, and layout configuration."""
from __future__ import annotations

import matplotlib.pyplot as plt


class ChartTheme:
    """Enterprise chart theme. Call ChartTheme.initialize() once before plotting."""

    @staticmethod
    def initialize() -> None:
        plt.rcParams["font.sans-serif"] = [
            "PingFang SC",
            "Microsoft YaHei",
            "SimHei",
            "Heiti SC",
            "Noto Sans CJK SC",
            "Arial Unicode MS",
        ]
        plt.rcParams["axes.unicode_minus"] = False
        plt.rcParams["figure.dpi"] = 200
        plt.rcParams["figure.figsize"] = (16, 9)
        plt.rcParams["figure.facecolor"] = "white"
        plt.rcParams["axes.facecolor"] = "white"
        plt.rcParams["axes.grid"] = True
        plt.rcParams["grid.alpha"] = 0.3
        plt.rcParams["grid.color"] = "#e0e0e0"
        plt.rcParams["font.size"] = 12
        plt.rcParams["axes.titlesize"] = 16
        plt.rcParams["axes.titleweight"] = "bold"
        plt.rcParams["axes.labelsize"] = 13
        plt.rcParams["xtick.labelsize"] = 10
        plt.rcParams["ytick.labelsize"] = 10
        plt.rcParams["legend.fontsize"] = 11
        plt.rcParams["lines.linewidth"] = 2
        plt.rcParams["savefig.dpi"] = 200
        plt.rcParams["savefig.bbox"] = "tight"
        plt.rcParams["savefig.pad_inches"] = 0.2
