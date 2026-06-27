"""Enterprise chart theme — unified font, color, DPI, and layout configuration."""
from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


def _find_chinese_font() -> str | None:
    """Find the first available Chinese-capable font on the system."""
    candidates = [
        "PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS",  # macOS
        "Microsoft YaHei", "SimHei", "KaiTi", "FangSong",  # Windows
        "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",  # Linux
    ]
    for f in fm.fontManager.ttflist:
        for c in candidates:
            if c.lower() in f.name.lower():
                return f.name
    return None


class ChartTheme:
    """Enterprise chart theme. Call ChartTheme.initialize() once before plotting."""

    @staticmethod
    def initialize() -> None:
        # Clear font cache to pick up system fonts
        try:
            fm._load_fontmanager(try_read_cache=False)
        except Exception:
            pass

        cn_font = _find_chinese_font()
        if cn_font:
            plt.rcParams["font.sans-serif"] = [cn_font, "DejaVu Sans"]
        else:
            plt.rcParams["font.sans-serif"] = [
                "PingFang SC", "Microsoft YaHei", "SimHei",
                "Heiti SC", "Noto Sans CJK SC", "Arial Unicode MS",
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
