"""Tests for Palette — enterprise color palette."""
from __future__ import annotations

import pytest

from chart.palette import Palette, PaletteColor


class TestPaletteColor:
    def test_named_tuple_fields(self):
        c = PaletteColor("#2F80ED", "蓝色")
        assert c.hex == "#2F80ED"
        assert c.name_cn == "蓝色"

    def test_immutable(self):
        c = PaletteColor("#2F80ED", "蓝色")
        with pytest.raises(AttributeError):
            c.hex = "#ff0000"


class TestPaletteConstants:
    def test_primary_color(self):
        assert Palette.PRIMARY.hex == "#2F80ED"
        assert Palette.PRIMARY.name_cn == "蓝色"

    def test_secondary_color(self):
        assert Palette.SECONDARY.hex == "#27AE60"
        assert Palette.SECONDARY.name_cn == "绿色"

    def test_success_color(self):
        assert Palette.SUCCESS.hex == "#219653"
        assert Palette.SUCCESS.name_cn == "深绿"

    def test_warning_color(self):
        assert Palette.WARNING.hex == "#F2994A"
        assert Palette.WARNING.name_cn == "橙色"

    def test_error_color(self):
        assert Palette.ERROR.hex == "#EB5757"
        assert Palette.ERROR.name_cn == "红色"

    def test_info_color(self):
        assert Palette.INFO.hex == "#9B51E0"
        assert Palette.INFO.name_cn == "紫色"

    def test_pink_color(self):
        assert Palette.PINK.hex == "#E91E63"
        assert Palette.PINK.name_cn == "粉红"

    def test_cyan_color(self):
        assert Palette.CYAN.hex == "#00BCD4"
        assert Palette.CYAN.name_cn == "青色"

    def test_series_length(self):
        assert len(Palette.SERIES) == 12

    def test_series_includes_all_basic_and_extended(self):
        expected = [
            Palette.PRIMARY, Palette.SECONDARY, Palette.SUCCESS,
            Palette.WARNING, Palette.ERROR, Palette.INFO,
            Palette.PINK, Palette.CYAN,
            Palette.EXT_AMBER, Palette.EXT_TEAL,
            Palette.EXT_INDIGO, Palette.EXT_BROWN,
        ]
        assert Palette.SERIES == expected


class TestGetSeriesColors:
    def test_get_one(self):
        colors = Palette.get_series_colors(1)
        assert len(colors) == 1
        assert colors[0] == Palette.PRIMARY

    def test_get_exact_series(self):
        colors = Palette.get_series_colors(12)
        assert len(colors) == 12
        assert colors == Palette.SERIES

    def test_get_beyond_series_cycles(self):
        """Requesting more than 12 colors should cycle base colors with hue shift."""
        colors = Palette.get_series_colors(14)
        assert len(colors) == 14
        # First 12 should match SERIES
        assert colors[:12] == Palette.SERIES
        # Colors 13+ should have generated names with suffix
        assert colors[12].name_cn == "蓝色_1"
        assert colors[13].name_cn == "绿色_1"


class TestGetColorName:
    def test_known_color(self):
        assert Palette.get_color_name("#2F80ED") == "蓝色"

    def test_unknown_color_returns_self(self):
        assert Palette.get_color_name("#123456") == "#123456"

    def test_case_sensitive(self):
        assert Palette.get_color_name("#2f80ed") == "#2f80ed"  # lowercase != uppercase
