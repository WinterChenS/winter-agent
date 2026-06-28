"""Enterprise color palette for charts — delegates to Palette in palette.py.

This module exists for backward compatibility. New code should import from
chart.palette directly.
"""
from chart.palette import Palette

# Backward-compatible single-color constants (old hex values removed —
# redirect to new Palette equivalents)
PRIMARY = Palette.PRIMARY.hex
SECONDARY = Palette.SECONDARY.hex
ACCENT = Palette.WARNING.hex       # mapped to closest new color
DANGER = Palette.ERROR.hex          # mapped
WARNING = Palette.WARNING.hex
SUCCESS = Palette.SUCCESS.hex
INFO = Palette.INFO.hex

# Backward-compatible palette list — use new Palette SERIES hex values
PALETTE = [pc.hex for pc in Palette.SERIES]
