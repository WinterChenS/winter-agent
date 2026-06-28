"""Enterprise color palette for charts with Chinese color names.

Usage:
    from chart.palette import Palette, PaletteColor

    # Get N series colors
    colors = Palette.get_series_colors(5)

    # Look up Chinese name by hex
    name = Palette.get_color_name("#2F80ED")  # -> "蓝色"

    # Direct access to named colors
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
    """Enterprise color palette with 12 named colors and series expansion."""

    # Base 8 colors
    PRIMARY = PaletteColor("#2F80ED", "蓝色")
    SECONDARY = PaletteColor("#27AE60", "绿色")
    SUCCESS = PaletteColor("#219653", "深绿")
    WARNING = PaletteColor("#F2994A", "橙色")
    ERROR = PaletteColor("#EB5757", "红色")
    INFO = PaletteColor("#9B51E0", "紫色")
    PINK = PaletteColor("#E91E63", "粉红")
    CYAN = PaletteColor("#00BCD4", "青色")

    # Extended 4 colors
    EXT_AMBER = PaletteColor("#FFC107", "琥珀")
    EXT_TEAL = PaletteColor("#009688", "青绿")
    EXT_INDIGO = PaletteColor("#3F51B5", "靛蓝")
    EXT_BROWN = PaletteColor("#795548", "棕色")

    SERIES: list[PaletteColor] = [
        PRIMARY, SECONDARY, SUCCESS,
        WARNING, ERROR, INFO,
        PINK, CYAN,
        EXT_AMBER, EXT_TEAL, EXT_INDIGO, EXT_BROWN,
    ]

    # Hex -> name_cn lookup cache (built lazily)
    _NAME_MAP: dict[str, str] | None = None

    @classmethod
    def get_series_colors(cls, n: int) -> list[PaletteColor]:
        """Return n colors from the SERIES palette.

        For n <= 12, returns the first n colors from SERIES.
        For n > 12, cycles the base 12 colors with a 30-degree hue shift
        per cycle, appending a numeric suffix to the color name.

        Args:
            n: Number of colors needed.

        Returns:
            List of n PaletteColor entries.
        """
        if n <= len(cls.SERIES):
            return cls.SERIES[:n]

        # More than 12: cycle with hue shift
        import matplotlib.colors as mcolors

        result: list[PaletteColor] = []
        cycle_index = 0
        while len(result) < n:
            base = cls.SERIES[cycle_index % len(cls.SERIES)]
            cycle = cycle_index // len(cls.SERIES)

            if cycle == 0:
                result.append(base)
            else:
                # Hue-shift the base color by 30 degrees per cycle
                rgb = mcolors.hex2color(base.hex)
                hsv = list(mcolors.rgb_to_hsv(rgb))
                hsv[0] = (hsv[0] + 30.0 / 360.0 * cycle) % 1.0
                shifted_rgb = mcolors.hsv_to_rgb(tuple(hsv))
                shifted_hex = mcolors.rgb2hex(shifted_rgb)
                result.append(PaletteColor(shifted_hex, f"{base.name_cn}_{cycle}"))

            cycle_index += 1

        return result[:n]

    @classmethod
    def get_color_name(cls, hex_color: str) -> str:
        """Look up the Chinese color name for a hex value.

        Args:
            hex_color: Hex color string (e.g., "#2F80ED").

        Returns:
            Chinese color name if found, otherwise the hex string itself.
        """
        if cls._NAME_MAP is None:
            cls._NAME_MAP = {pc.hex: pc.name_cn for pc in cls.SERIES}
        return cls._NAME_MAP.get(hex_color, hex_color)
