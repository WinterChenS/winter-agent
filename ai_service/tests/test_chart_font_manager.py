"""Tests for FontManager — font discovery, caching, and validation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pytest

from chart.font_manager import FontManager


class TestFontManagerInit:
    def test_initialize_is_idempotent(self):
        FontManager._initialized = False
        FontManager._font_properties = None
        with patch.object(FontManager, "_discover", wraps=FontManager._discover) as mock:
            FontManager.initialize(force=False)
            FontManager.initialize(force=False)
            assert mock.call_count == 1

    def test_initialize_force_rescans(self):
        FontManager._initialized = False
        FontManager._font_properties = None
        with patch.object(FontManager, "_discover", wraps=FontManager._discover) as mock:
            FontManager.initialize(force=False)
            FontManager.initialize(force=True)
            assert mock.call_count == 2

    def test_get_cn_font_auto_init(self):
        FontManager._initialized = False
        FontManager._font_properties = None
        fp = FontManager.get_cn_font()
        assert fp is not None
        assert FontManager._initialized is True


class TestFontDiscovery:
    @patch("chart.font_manager.fm.fontManager.ttflist", new_callable=list)
    def test_discover_macos_pingfang(self, mock_ttflist):
        mock_font = MagicMock(spec=fm.FontEntry)
        mock_font.name = "PingFang SC"
        mock_ttflist.append(mock_font)
        fp = FontManager._discover()
        assert fp is not None

    @patch("chart.font_manager.fm.fontManager.ttflist", new_callable=list)
    def test_discover_fallback_to_default(self, mock_ttflist):
        mock_ttflist.clear()
        with patch("chart.font_manager.logger") as mock_log:
            fp = FontManager._discover()
            assert fp is not None
            mock_log.warning.assert_called_once()

    def test_validate_figure_fonts_no_text(self):
        fig, _ = plt.subplots()
        warnings = FontManager.validate_figure_fonts(fig)
        assert isinstance(warnings, list)
        plt.close(fig)
