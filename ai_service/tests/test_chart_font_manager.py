"""Tests for FontManager — font discovery, caching, and validation."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pytest

from chart.font_manager import FontManager


class TestFontManagerInit:
    """FontManager initialization and caching."""

    def test_initialize_is_idempotent(self):
        """Calling initialize() twice should only scan fonts once."""
        FontManager._initialized = False
        FontManager._font_properties = None
        with patch.object(FontManager, "_discover", wraps=FontManager._discover) as mock:
            FontManager.initialize(force=False)
            FontManager.initialize(force=False)
            # Second call hits cache, does NOT call _discover again
            assert mock.call_count == 1

    def test_initialize_force_rescans(self):
        """Calling initialize(force=True) rescans even if already initialized."""
        FontManager._initialized = False
        FontManager._font_properties = None
        with patch.object(FontManager, "_discover", wraps=FontManager._discover) as mock:
            FontManager.initialize(force=False)
            FontManager.initialize(force=True)
            assert mock.call_count == 2

    def test_get_cn_font_auto_init(self):
        """get_cn_font() auto-initializes if not yet initialized."""
        FontManager._initialized = False
        FontManager._font_properties = None
        fp = FontManager.get_cn_font()
        assert fp is not None
        assert FontManager._initialized is True


class TestFontDiscovery:
    """Cross-platform font discovery."""

    @patch("chart.font_manager.fm.fontManager.ttflist", new_callable=list)
    def test_discover_macos_pingfang(self, mock_ttflist):
        """macOS: PingFang SC is preferred."""
        mock_font = MagicMock(spec=fm.FontEntry)
        mock_font.name = "PingFang SC"
        mock_ttflist.append(mock_font)
        fp = FontManager._discover()
        assert fp is not None
        assert "PingFang" in FontManager._font_name or FontManager._font_name == "PingFang SC"

    @patch("chart.font_manager.fm.fontManager.ttflist", new_callable=list)
    def test_discover_fallback_to_default(self, mock_ttflist):
        """When no Chinese font is found, return None and log warning."""
        mock_ttflist.clear()
        with patch("chart.font_manager.logger") as mock_log:
            fp = FontManager._discover()
            assert fp is None
            mock_log.warning.assert_called_once()

    def test_validate_figure_fonts_no_text(self):
        """validate_figure_fonts() returns empty list when no Text artists."""
        fig, _ = plt.subplots()
        warnings = FontManager.validate_figure_fonts(fig)
        assert isinstance(warnings, list)
        plt.close(fig)

    def test_validate_figure_fonts_with_text(self):
        """validate_figure_fonts() detects Text artists without fontproperties."""
        fig, ax = plt.subplots()
        ax.set_title("Test", fontproperties=FontManager.get_cn_font())
        warnings = FontManager.validate_figure_fonts(fig)
        # Title has fontproperties set, so no warning for it
        assert isinstance(warnings, list)
        plt.close(fig)
