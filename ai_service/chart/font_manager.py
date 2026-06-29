"""FontManager — module-level singleton for Chinese font discovery and caching.

Usage:
    from chart.font_manager import FontManager
    cn_font = FontManager.get_cn_font()  # auto-initializes on first call
    FontManager.initialize(force=True)     # force re-scan
"""
from __future__ import annotations

import logging

import matplotlib.font_manager as fm
from matplotlib.font_manager import FontProperties

logger = logging.getLogger(__name__)


class FontManager:
    """Module-level singleton for font management."""

    _font_properties: FontProperties | None = None
    _font_name: str = ""
    _initialized: bool = False

    _MACOS_CANDIDATES = [
        "PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS",
    ]
    _WINDOWS_CANDIDATES = [
        "Microsoft YaHei", "SimHei", "KaiTi",
    ]
    _LINUX_CANDIDATES = [
        "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei",
    ]

    @classmethod
    def initialize(cls, force: bool = False) -> None:
        if cls._initialized and not force:
            return
        cls._font_properties = cls._discover()
        cls._initialized = True

    @classmethod
    def get_cn_font(cls) -> FontProperties:
        if not cls._initialized:
            cls.initialize()
        return cls._font_properties or FontProperties()

    @classmethod
    def get_font_name(cls) -> str:
        if not cls._initialized:
            cls.initialize()
        return cls._font_name or "default"

    @classmethod
    def _discover(cls) -> FontProperties | None:
        import os
        import sys as _sys

        env_path = os.environ.get("CHART_FONT_PATH")
        if env_path and os.path.isfile(env_path):
            logger.info("Using CHART_FONT_PATH: %s", env_path)
            cls._font_name = os.path.basename(env_path)
            return FontProperties(fname=env_path)

        if _sys.platform == "darwin":
            candidates = cls._MACOS_CANDIDATES
        elif _sys.platform == "win32":
            candidates = cls._WINDOWS_CANDIDATES
        else:
            candidates = cls._LINUX_CANDIDATES

        for entry in fm.fontManager.ttflist:
            for candidate in candidates:
                if candidate.lower() in entry.name.lower():
                    cls._font_name = entry.name
                    logger.info("Discovered font: %s", entry.name)
                    return FontProperties(family=entry.name)

        logger.warning(
            "No Chinese-capable font found. Charts may not display Chinese text correctly. "
            "Set CHART_FONT_PATH to specify a font file."
        )
        return FontProperties()

    @classmethod
    def validate_figure_fonts(cls, fig) -> list[str]:
        from matplotlib.text import Text

        warnings: list[str] = []
        for artist in fig.findobj(match=Text):
            fp = artist.get_fontproperties()
            if fp is None or fp.get_family() == ["sans-serif"]:
                text_preview = artist.get_text()[:30]
                warnings.append(
                    f"Text '{text_preview}' is missing explicit fontproperties"
                )
        return warnings
