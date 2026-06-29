"""Enterprise color palette for charts — delegates to Palette in palette.py.

This module exists for backward compatibility. New code should import from
chart.palette directly.
"""
from chart.palette import Palette

PRIMARY = Palette.PRIMARY.hex
SECONDARY = Palette.SECONDARY.hex
ACCENT = Palette.WARNING.hex
DANGER = Palette.ERROR.hex
WARNING = Palette.WARNING.hex
SUCCESS = Palette.SUCCESS.hex
INFO = Palette.INFO.hex

PALETTE = [pc.hex for pc in Palette.SERIES]
