"""Enterprise color palette for charts with Chinese color names.

Usage:
    from chart.palette import Palette, PaletteColor

    colors = Palette.get_series_colors(5)
    name = Palette.get_color_name("#2F80ED")  # -> "蓝色"
    primary = Palette.PRIMARY
"""
from __future__ import annotations

import math
from typing import NamedTuple


class PaletteColor(NamedTuple):
    """A named color entry with hex and Chinese name."""
    hex: str
    name_cn: str


class Palette:
    """Enterprise color palette with 7 named colors and 12-item series."""

    PRIMARY   = PaletteColor("#2F80ED", "蓝色")
    SECONDARY = PaletteColor("#27AE60", "绿色")
    SUCCESS   = PaletteColor("#219653", "深绿")
    WARNING   = PaletteColor("#F2994A", "橙色")
    ERROR     = PaletteColor("#EB5757", "红色")
    INFO      = PaletteColor("#9B51E0", "紫色")
    NEUTRAL   = PaletteColor("#828282", "灰色")

    # 12-item series: 7 base + 5 hue-shifted
    _BASE = [PRIMARY, SECONDARY, SUCCESS, WARNING, ERROR, INFO, NEUTRAL]

    SERIES: list[PaletteColor] = list(_BASE)  # extended below

    _NAME_MAP: dict[str, str] | None = None

    @classmethod
    def __init_subclass__(cls, **kwargs):
        pass

    @classmethod
    def _build_series(cls) -> list[PaletteColor]:
        """Build the 12-color SERIES from 7 base + 5 hue-shifted colors."""
        import matplotlib.colors as mcolors

        result = list(cls._BASE)
        while len(result) < 12:
            idx = len(result) - len(cls._BASE)
            base = cls._BASE[idx % len(cls._BASE)]
            rgb = mcolors.hex2color(base.hex)
            hsv = list(mcolors.rgb_to_hsv(rgb))
            shift = 30.0 / 360.0
            hsv[0] = (hsv[0] + shift) % 1.0
            shifted_hex = mcolors.rgb2hex(mcolors.hsv_to_rgb(tuple(hsv)))
            result.append(PaletteColor(shifted_hex, f"{base.name_cn}_v{idx + 1}"))
        return result


# Build SERIES at module load time
Palette.SERIES = Palette._build_series()


# Build name lookup cache
Palette._NAME_MAP = {pc.hex: pc.name_cn for pc in Palette.SERIES}


def _patch_classmethods():
    """Attach classmethods after SERIES is finalized."""

    @classmethod
    def get_series_colors(cls, n: int) -> list[PaletteColor]:
        if n <= len(cls.SERIES):
            return cls.SERIES[:n]
        import matplotlib.colors as mcolors
        result: list[PaletteColor] = []
        cycle_index = 0
        while len(result) < n:
            base = cls.SERIES[cycle_index % len(cls.SERIES)]
            cycle = cycle_index // len(cls.SERIES)
            if cycle == 0:
                result.append(base)
            else:
                rgb = mcolors.hex2color(base.hex)
                hsv = list(mcolors.rgb_to_hsv(rgb))
                hsv[0] = (hsv[0] + 30.0 / 360.0 * cycle) % 1.0
                shifted_hex = mcolors.rgb2hex(mcolors.hsv_to_rgb(tuple(hsv)))
                result.append(PaletteColor(shifted_hex, f"{base.name_cn}_{cycle}"))
            cycle_index += 1
        return result[:n]

    @classmethod
    def get_color_name(cls, hex_color: str) -> str:
        if cls._NAME_MAP is None:
            cls._NAME_MAP = {pc.hex: pc.name_cn for pc in cls.SERIES}
        return cls._NAME_MAP.get(hex_color, hex_color)

    Palette.get_series_colors = get_series_colors
    Palette.get_color_name = get_color_name


_patch_classmethods()
