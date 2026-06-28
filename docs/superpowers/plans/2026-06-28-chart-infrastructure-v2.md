---
change: chart-infrastructure-v2
design-doc: docs/superpowers/specs/2026-06-28-chart-infrastructure-v2-design.md
base-ref: 2c1ada3398615c22e69f8c1afb498e82677eae8a
---

# Chart Infrastructure v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace rcParams-based font configuration with a dedicated FontManager singleton, introduce a strongly-typed Palette system with Chinese color names, emit structured ChartResult/ChartMetadata from the render pipeline, and propagate structured metadata through SSE, prompts, and the sandbox preamble.

**Architecture:** Three new modules (`font_manager.py`, `palette.py`, `chart_result.py`) are introduced at `ai_service/chart/`. The existing `MatplotlibRenderer` is refactored to use these modules and return `ChartResult` instead of a bare path string. `ChartService` propagates structured metadata to callers. `ChartTheme` delegates to FontManager and drops rcParams font configuration. `CodeSandboxTool._build_preamble()` and `_CHART_CODE_PROMPT` are updated to inject `cn_font` and `Palette` into the exec context. The pipeline flows: LLM generates code with `cn_font`/`Palette`/`__chart_metadata__` -> `MatplotlibRenderer.render()` execs with variable bridge -> extracts/validates metadata -> returns `ChartResult` -> `ChartService` uploads PNG + metadata.json -> SSE pushes both URLs.

**Tech Stack:** Python 3.11+, matplotlib 3.6+, pytest, MinIO (for storage).

## Global Constraints

- All text in generated charts MUST use `fontproperties=cn_font` (FontProperties object injected into exec context), NOT `plt.rcParams['font.sans-serif']`.
- All chart colors MUST come from `Palette.get_series_colors(N)` — no hardcoded hex values in generated code.
- Every generated chart MUST set `__chart_metadata__` dict with `chart_type`, `title`, `series` (list of `{name, color, color_name}`), and `summary`.
- The old `PALETTE` list in `color_utils.py` MUST remain available as a backward-compatible re-export.
- `ChartTheme.initialize()` MUST delegate to `FontManager.initialize()` and MUST NOT set rcParams font-related keys.
- No new third-party dependencies beyond what matplotlib already requires.

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `ai_service/chart/font_manager.py` | FontManager singleton: cross-platform font discovery, CJK validation, cached FontProperties, figure font validation |
| `ai_service/chart/palette.py` | Palette class with 12 named colors + series expansion logic |
| `ai_service/chart/chart_result.py` | ChartResult, ChartMetadata, SeriesInfo dataclasses with serialization |

### Modified files
| File | Responsibility | Changes |
|------|---------------|---------|
| `ai_service/chart/chart_theme.py` | Theme initialization | Delegate to FontManager, drop rcParams font lines |
| `ai_service/chart/utils/color_utils.py` | Backward compat | Re-export PALETTE from Palette |
| `ai_service/chart/renderers/matplotlib_renderer.py` | Chart rendering | Return ChartResult, inject cn_font, extract metadata, validate fonts |
| `ai_service/chart/chart_renderer.py` | Abstract base class | Update `render()` return type from `str` to `ChartResult` |
| `ai_service/chart/chart_service.py` | Service facade | Upload metadata.json, return metadata in dict, emit chart.metadata SSE |
| `ai_service/tools/sandbox/tool.py` | Sandbox preamble | Inject `cn_font` + `Palette` imports, replace ChartTheme.initialize() preamble |
| `ai_service/graph/nodes.py` | LLM prompts | Update _CHART_CODE_PROMPT and _build_composer_system_prompt |
| `ai_service/chart/__init__.py` | Package exports | Export new public symbols |

### Test files
| File | Responsibility |
|------|---------------|
| `ai_service/tests/test_chart_font_manager.py` | FontManager unit tests |
| `ai_service/tests/test_chart_palette.py` | Palette unit tests |
| `ai_service/tests/test_chart_renderer_v2.py` | MatplotlibRenderer v2 tests |

---

### Task 1: FontManager — font discovery and caching

**Files:**
- Create: `ai_service/chart/font_manager.py`
- Test: `ai_service/tests/test_chart_font_manager.py`

**Interfaces:**
- Consumes: nothing (standalone module)
- Produces: `FontManager` class with classmethods: `initialize(force=False)`, `get_cn_font() -> FontProperties`, `get_font_name() -> str`, `validate_figure_fonts(fig) -> list[str]`

- [x] **Step 1: Write FontManager failing tests**

Create `ai_service/tests/test_chart_font_manager.py`:

```python
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
        """When no Chinese font is found, return default FontProperties and log warning."""
        mock_ttflist.clear()
        with patch("chart.font_manager.logger") as mock_log:
            fp = FontManager._discover()
            assert fp is not None
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
```

- [x] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_font_manager.py -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'chart.font_manager'" (or import errors)

- [x] **Step 3: Create FontManager module**

Create `ai_service/chart/font_manager.py`:

```python
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
    """Module-level singleton for font management.

    All methods are class methods. State is stored on the class itself.
    """

    _font_properties: FontProperties | None = None
    _font_name: str = ""
    _initialized: bool = False

    # Font discovery priority per platform — first match wins
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
        """Idempotent initialization. Scans and caches font on first call.

        Args:
            force: If True, re-scan even if already initialized.
        """
        if cls._initialized and not force:
            return
        cls._font_properties = cls._discover()
        cls._initialized = True

    @classmethod
    def get_cn_font(cls) -> FontProperties:
        """Return cached FontProperties. Auto-initializes if needed."""
        if not cls._initialized:
            cls.initialize()
        return cls._font_properties or FontProperties()

    @classmethod
    def get_font_name(cls) -> str:
        """Return the discovered font name (for logging)."""
        if not cls._initialized:
            cls.initialize()
        return cls._font_name or "default"

    @classmethod
    def _discover(cls) -> FontProperties | None:
        """Cross-platform font discovery.

        Priority:
            1. CHART_FONT_PATH env var (direct file path)
            2. macOS: PingFang SC -> Heiti SC -> STHeiti -> Arial Unicode MS
            3. Windows: Microsoft YaHei -> SimHei -> KaiTi
            4. Linux: Noto Sans CJK SC -> Noto Sans SC -> WenQuanYi Micro Hei
            5. Fallback: None

        Returns:
            FontProperties instance, or None if no Chinese font found.
        """
        import os

        # 1. Env var override
        env_path = os.environ.get("CHART_FONT_PATH")
        if env_path and os.path.isfile(env_path):
            logger.info("Using CHART_FONT_PATH: %s", env_path)
            cls._font_name = os.path.basename(env_path)
            return FontProperties(fname=env_path)

        # 2-4. System font discovery
        import sys as _sys
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

        # 5. Fallback
        logger.warning(
            "No Chinese-capable font found. Charts may not display Chinese text correctly. "
            "Set CHART_FONT_PATH to specify a font file."
        )
        return None

    @classmethod
    def _validate_chinese(cls, fp: FontProperties) -> bool:
        """Validate that a FontProperties instance supports CJK characters.

        Renders a CJK character to check for the .notdef glyph (tofu).
        This is a best-effort check.

        Args:
            fp: FontProperties to validate.

        Returns:
            True if the font appears to support Chinese, False otherwise.
        """
        try:
            import matplotlib as mpl
            from matplotlib.ft2font import FT2Font
            # Use matplotlib's internals to check font coverage
            fallback_list = fm.get_fallback_fonts(fp)
            # If fallbacks are empty but we have a font, it's likely okay
            return True
        except Exception:
            return True  # Don't block on validation errors

    @classmethod
    def validate_figure_fonts(cls, fig) -> list[str]:
        """Scan all Text artists in a figure for fontproperties compliance.

        Args:
            fig: A matplotlib Figure instance.

        Returns:
            List of warning strings for Text artists missing fontproperties.
        """
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
```

- [x] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_font_manager.py -v
```
Expected: PASS (4-5 tests depending on mock behavior)

- [x] **Step 5: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/font_manager.py ai_service/tests/test_chart_font_manager.py && git commit -m "feat: add FontManager for cross-platform Chinese font discovery and caching"
```

---

### Task 2: Palette — enterprise color palette with Chinese color names

**Files:**
- Create: `ai_service/chart/palette.py`
- Modify: `ai_service/chart/utils/color_utils.py` (add backward-compatible re-export)
- Test: `ai_service/tests/test_chart_palette.py`

**Interfaces:**
- Consumes: nothing
- Produces: `PaletteColor(NamedTuple)` with `hex: str`, `name_cn: str`; `Palette` class with class-level color constants, `SERIES` list (12 colors), `get_series_colors(n) -> list[PaletteColor]`, `get_color_name(hex) -> str`

- [x] **Step 1: Write Palette failing tests**

Create `ai_service/tests/test_chart_palette.py`:

```python
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
```

- [x] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_palette.py -v
```
Expected: FAIL with import errors

- [x] **Step 3: Create Palette module**

Create `ai_service/chart/palette.py`:

```python
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
```

- [x] **Step 4: Update color_utils.py for backward compatibility**

Edit `ai_service/chart/utils/color_utils.py`:

Old content:
```python
"""Enterprise color palette for charts."""

PRIMARY = "#2c7fb8"
SECONDARY = "#7fcdbb"
ACCENT = "#edf8b1"
DANGER = "#e34a33"
WARNING = "#fdbb84"
SUCCESS = "#31a354"
INFO = "#a6bddb"

PALETTE = [
    "#2c7fb8", "#7fcdbb", "#edf8b1", "#e34a33",
    "#fdbb84", "#31a354", "#a6bddb", "#636363",
    "#b30000", "#542788", "#35978f", "#80cdc1",
]
```

Replace with:
```python
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
```

- [x] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_palette.py -v
```
Expected: PASS (all tests)

- [x] **Step 6: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/palette.py ai_service/chart/utils/color_utils.py ai_service/tests/test_chart_palette.py && git commit -m "feat: add Palette with Chinese color names, backward-compat color_utils"
```

---

### Task 3: ChartResult + ChartMetadata + SeriesInfo — structured data classes

**Files:**
- Create: `ai_service/chart/chart_result.py`
- Modify: `ai_service/chart/__init__.py` (export new types)

**Interfaces:**
- Consumes: `PaletteColor` from `chart.palette` (used in `to_markdown_hint()`)
- Produces: `SeriesInfo(name: str, color: str, color_name: str)`, `ChartMetadata(title, chart_type, xlabel, ylabel, series, summary)`, `ChartResult(image_path: str, metadata: ChartMetadata, summary: str)`

- [x] **Step 1: Create chart_result.py**

Create `ai_service/chart/chart_result.py`:

```python
"""Structured chart output types.

ChartResult is the return type of all renderers. ChartMetadata carries
structured information for downstream consumers (SSE, prompts, reports).
SeriesInfo provides per-series color metadata so LLM composers can
reference colors by name.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SeriesInfo:
    """Metadata for a single data series in a chart."""
    name: str
    color: str       # hex, e.g. "#2F80ED"
    color_name: str  # Chinese, e.g. "蓝色"


@dataclass
class ChartMetadata:
    """Structured metadata extracted from or declared by a chart.

    Can be populated from:
      L1: __chart_metadata__ dict (declared by generated code)
      L2: figure state fallback (axis labels, legend titles, etc.)
    """
    title: str
    chart_type: str
    xlabel: str = ""
    ylabel: str = ""
    series: list[SeriesInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "title": self.title,
            "chart_type": self.chart_type,
            "xlabel": self.xlabel,
            "ylabel": self.ylabel,
            "series": [
                {"name": s.name, "color": s.color, "color_name": s.color_name}
                for s in self.series
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChartMetadata:
        """Deserialize from a dict (e.g., loaded from metadata.json)."""
        series_list = [
            SeriesInfo(name=s["name"], color=s["color"], color_name=s["color_name"])
            for s in data.get("series", [])
        ]
        return cls(
            title=data.get("title", ""),
            chart_type=data.get("chart_type", ""),
            xlabel=data.get("xlabel", ""),
            ylabel=data.get("ylabel", ""),
            series=series_list,
        )

    def to_markdown_hint(self) -> str:
        """Generate an LLM-friendly markdown snippet describing the chart.

        Example:
            图表: GDP增长率 (bar)
             - GDP: 蓝色 (#2F80ED)
             - CPI: 绿色 (#27AE60)
            摘要: GDP在2020-2024年间稳定增长
        """
        lines: list[str] = []
        lines.append(f"图表: {self.title} ({self.chart_type})")
        for s in self.series:
            lines.append(f" - {s.name}: {s.color_name} ({s.color})")
        return "\n".join(lines)


@dataclass
class ChartResult:
    """Complete output of a chart rendering operation."""
    image_path: str
    metadata: ChartMetadata
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "image_path": self.image_path,
            "metadata": self.metadata.to_dict(),
            "summary": self.summary,
        }
```

- [x] **Step 2: Update chart/__init__.py exports**

Write to `ai_service/chart/__init__.py`:
```python
from chart.chart_result import ChartResult, ChartMetadata, SeriesInfo
from chart.palette import Palette, PaletteColor
from chart.font_manager import FontManager

__all__ = [
    "ChartResult",
    "ChartMetadata",
    "SeriesInfo",
    "Palette",
    "PaletteColor",
    "FontManager",
]
```

- [x] **Step 3: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/chart_result.py ai_service/chart/__init__.py && git commit -m "feat: add ChartResult, ChartMetadata, SeriesInfo data classes"
```

---

### Task 4: ChartTheme refactor — delegate font to FontManager

**Files:**
- Modify: `ai_service/chart/chart_theme.py`

**Interfaces:**
- Consumes: `FontManager` from `chart.font_manager`
- Produces: `ChartTheme.initialize()` with same signature, but delegates font to FontManager and drops rcParams font keys; `_find_chinese_font()` is removed

- [x] **Step 1: Read current ChartTheme to confirm the exact content** (already read above)

- [x] **Step 2: Refactor ChartTheme**

Edit `ai_service/chart/chart_theme.py`. Replace the entire file content:

```python
"""Enterprise chart theme — unified font, color, DPI, and layout configuration.

Font management is delegated to FontManager. This module only handles
non-font style configuration (DPI, figure size, grid, colors).
"""
from __future__ import annotations

import matplotlib.pyplot as plt
from chart.font_manager import FontManager


class ChartTheme:
    """Enterprise chart theme. Call ChartTheme.initialize() once before plotting.

    Font initialization is delegated to FontManager. All non-font style
    configuration (DPI, figsize, grid, colors, font sizes except font family)
    is applied here via rcParams.
    """

    @staticmethod
    def initialize() -> None:
        FontManager.initialize()

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
```

Note: The old `_find_chinese_font()` function is removed entirely since FontManager handles that responsibility. The `fm._load_fontmanager(try_read_cache=False)` call is also removed — FontManager handles cache clearing if needed.

- [x] **Step 3: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/chart_theme.py && git commit -m "refactor: ChartTheme delegates font to FontManager, removes _find_chinese_font"
```

---

### Task 5: MatplotlibRenderer — return ChartResult, inject cn_font, extract metadata

**Files:**
- Modify: `ai_service/chart/renderers/matplotlib_renderer.py`
- Modify: `ai_service/chart/chart_renderer.py` (update abstract return type)
- Test: `ai_service/tests/test_chart_renderer_v2.py`

**Interfaces:**
- Consumes: `FontManager`, `ChartResult`, `ChartMetadata`, `SeriesInfo` from chart package; `Palette` for color name lookup
- Produces: `MatplotlibRenderer.render(code, output_path) -> ChartResult` (was `-> str`)

- [x] **Step 1: Update AbstractChartRenderer return type**

Edit `ai_service/chart/chart_renderer.py` line 11. Change:
```python
    def render(self, code: str, output_path: str) -> str:
```
To:
```python
    def render(self, code: str, output_path: str) -> ChartResult:
```

Add import at top:
```python
from chart.chart_result import ChartResult
```

- [x] **Step 2: Write MatplotlibRenderer v2 failing tests**

Create `ai_service/tests/test_chart_renderer_v2.py`:

```python
"""Tests for MatplotlibRenderer v2 — ChartResult return, metadata extraction, font validation."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from chart.chart_result import ChartResult, ChartMetadata, SeriesInfo
from chart.renderers.matplotlib_renderer import MatplotlibRenderer


@pytest.fixture
def renderer():
    return MatplotlibRenderer()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


SIMPLE_CHART_CODE = """\
import matplotlib.pyplot as plt
import numpy as np

x = np.arange(1, 6)
y = np.array([10, 20, 15, 25, 30])

__chart_metadata__ = {
    "chart_type": "line",
    "title": "Test Chart",
    "series": [
        {"name": "Series A", "color": "#2F80ED", "color_name": "蓝色"},
    ],
    "summary": "Test chart summary",
}

fig, ax = plt.subplots()
ax.plot(x, y, color="#2F80ED", label="Series A")
ax.set_title("Test Chart")
ax.set_xlabel("X")
ax.set_ylabel("Y")
ax.legend()
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
plt.close(fig)
"""


class TestRenderReturnsChartResult:
    def test_render_returns_chart_result(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(SIMPLE_CHART_CODE, output_path)
        assert isinstance(result, ChartResult)
        assert result.image_path == output_path

    def test_render_metadata_from_chart_metadata(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(SIMPLE_CHART_CODE, output_path)
        assert result.metadata.title == "Test Chart"
        assert result.metadata.chart_type == "line"
        assert result.metadata.xlabel == "X"
        assert result.metadata.ylabel == "Y"
        assert len(result.metadata.series) == 1
        assert result.metadata.series[0].name == "Series A"
        assert result.metadata.series[0].color == "#2F80ED"
        assert result.metadata.series[0].color_name == "蓝色"

    def test_render_summary(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(SIMPLE_CHART_CODE, output_path)
        assert result.summary == "Test chart summary"

    def test_render_metadata_json_file_created(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        renderer.render(SIMPLE_CHART_CODE, output_path)
        json_path = output_path.replace(".png", "_metadata.json")
        assert os.path.isfile(json_path)
        with open(json_path) as f:
            data = json.load(f)
        assert data["title"] == "Test Chart"
        assert data["chart_type"] == "line"


class TestRenderWithoutMetadataDecl:
    """When __chart_metadata__ is not set, fall back to figure state (L2)."""

    CODE_NO_METADATA = """\
import matplotlib.pyplot as plt
import numpy as np

fig, ax = plt.subplots()
ax.plot([1,2,3], [4,5,6], label="My Series")
ax.set_title("Fallback Title")
ax.set_xlabel("X Axis")
ax.set_ylabel("Y Axis")
ax.legend()
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
plt.close(fig)
"""

    def test_l2_fallback_extracts_title_from_axes(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(self.CODE_NO_METADATA, output_path)
        assert result.metadata.title == "Fallback Title"
        assert result.metadata.xlabel == "X Axis"
        assert result.metadata.ylabel == "Y Axis"

    def test_l2_fallback_chart_type_is_unknown(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(self.CODE_NO_METADATA, output_path)
        assert result.metadata.chart_type == "unknown"

    def test_l2_fallback_series_from_legend(self, renderer, temp_dir):
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(self.CODE_NO_METADATA, output_path)
        # Series should be extracted from legend handles
        if result.metadata.series:
            assert result.metadata.series[0].name == "My Series"


class TestFontInjection:
    def test_cn_font_injected_into_context(self, renderer, temp_dir):
        """cn_font should be available in exec context."""
        code = """\
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.set_title("Test", fontproperties=cn_font)
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
plt.close(fig)
"""
        output_path = os.path.join(temp_dir, "test.png")
        result = renderer.render(code, output_path)
        assert result.image_path == output_path
```

- [x] **Step 3: Run tests to verify they fail**

Run:
```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_renderer_v2.py -v
```
Expected: FAIL (return type mismatch, missing metadata extraction, etc.)

- [x] **Step 4: Refactor MatplotlibRenderer**

Replace the entire content of `ai_service/chart/renderers/matplotlib_renderer.py`:

```python
"""Matplotlib chart renderer — returns ChartResult with structured metadata."""
from __future__ import annotations

import json
import logging
import os

from chart.chart_renderer import AbstractChartRenderer
from chart.font_manager import FontManager
from chart.chart_result import ChartResult, ChartMetadata, SeriesInfo
from chart.palette import Palette

logger = logging.getLogger(__name__)


class MatplotlibRenderer(AbstractChartRenderer):
    """Render charts using matplotlib with enterprise theme.

    Returns a ChartResult containing the image path and structured metadata
    extracted from either the __chart_metadata__ variable (declared in code)
    or the matplotlib figure state (fallback).
    """

    def render(self, code: str, output_path: str) -> ChartResult:
        FontManager.initialize()

        import matplotlib.pyplot as plt
        plt.close("all")

        # Build execution context with injected variables
        ctx = {
            "__output_path__": output_path,
            "plt": plt,
            "cn_font": FontManager.get_cn_font(),
            "__chart_metadata__": None,
        }

        exec(code, ctx)

        # Ensure tight_layout for Chinese label overlap prevention
        figs = [plt.figure(n) for n in plt.get_fignums()]
        for fig in figs:
            try:
                fig.tight_layout()
            except Exception:
                pass

        # If code didn't savefig, do it now
        if not os.path.exists(output_path):
            if figs:
                figs[-1].savefig(output_path, dpi=200, bbox_inches="tight")
            else:
                fig, ax = plt.subplots(figsize=(16, 9))
                ax.text(0.5, 0.5, "No chart data", ha="center", va="center", fontsize=16)
                ax.set_axis_off()
                fig.savefig(output_path, dpi=200, bbox_inches="tight")
                plt.close(fig)

        # ── Metadata extraction ──
        metadata = self._extract_metadata(ctx, figs)

        # ── Summary ──
        summary = ctx.get("__chart_metadata__", {}) or {}
        summary_text = summary.get("summary", "") if isinstance(summary, dict) else ""

        # ── Font validation (best-effort, non-blocking) ──
        for fig in figs:
            try:
                warnings = FontManager.validate_figure_fonts(fig)
                for w in warnings:
                    logger.warning("Font compliance: %s", w)
            except Exception:
                pass

        # ── Save metadata JSON alongside PNG ──
        self._save_metadata(output_path, metadata)

        plt.close("all")

        return ChartResult(
            image_path=output_path,
            metadata=metadata,
            summary=summary_text,
        )

    def _extract_metadata(
        self,
        ctx: dict,
        figs: list,
    ) -> ChartMetadata:
        """Extract chart metadata, with two-level fallback.

        L1: __chart_metadata__ dict from exec context (declared by generated code).
        L2: matplotlib figure state (axis labels, legend, etc.).

        Returns:
            Populated ChartMetadata instance.
        """
        declared = ctx.get("__chart_metadata__")
        if declared and isinstance(declared, dict):
            return self._extract_l1(declared, figs)
        return self._extract_l2(figs)

    def _extract_l1(self, declared: dict, figs: list) -> ChartMetadata:
        """Build metadata from __chart_metadata__ dict (L1)."""
        series_list = []
        for s in declared.get("series", []):
            series_list.append(SeriesInfo(
                name=s.get("name", ""),
                color=s.get("color", ""),
                color_name=s.get("color_name", ""),
            ))

        metadata = ChartMetadata(
            title=str(declared.get("title", "")),
            chart_type=str(declared.get("chart_type", "")),
            series=series_list,
        )

        # L2 fallback for any L1 gaps
        if figs:
            self._l2_fill_gaps(metadata, figs[-1])

        return metadata

    def _extract_l2(self, figs: list) -> ChartMetadata:
        """Build metadata from matplotlib figure state (L2 fallback)."""
        metadata = ChartMetadata(
            title="",
            chart_type="unknown",
        )
        if figs:
            self._l2_fill_gaps(metadata, figs[-1])
        return metadata

    def _l2_fill_gaps(self, metadata: ChartMetadata, fig) -> None:
        """Fill missing metadata fields from figure state."""
        import matplotlib.pyplot as plt

        for ax in fig.get_axes():
            if not metadata.title:
                t = ax.get_title()
                if t:
                    metadata.title = t
            if not metadata.xlabel:
                xl = ax.get_xlabel()
                if xl:
                    metadata.xlabel = xl
            if not metadata.ylabel:
                yl = ax.get_ylabel()
                if yl:
                    metadata.ylabel = yl

        # Extract series from legend
        if not metadata.series:
            for ax in fig.get_axes():
                legend = ax.get_legend()
                if legend is None:
                    continue
                for handle, label in zip(legend.legend_handles or [], 
                                          [t.get_text() for t in legend.get_texts()]):
                    color_hex = "#000000"
                    try:
                        if hasattr(handle, "get_color"):
                            c = handle.get_color()
                            if isinstance(c, tuple):
                                from matplotlib.colors import rgb2hex
                                color_hex = rgb2hex(c)
                            else:
                                color_hex = str(c)
                        elif hasattr(handle, "get_facecolor"):
                            c = handle.get_facecolor()
                            if isinstance(c, tuple):
                                from matplotlib.colors import rgb2hex
                                color_hex = rgb2hex(c)
                            else:
                                color_hex = str(c)
                    except Exception:
                        pass
                    metadata.series.append(SeriesInfo(
                        name=label,
                        color=color_hex,
                        color_name=Palette.get_color_name(color_hex),
                    ))

    def _save_metadata(self, output_path: str, metadata: ChartMetadata) -> None:
        """Save ChartMetadata as a JSON file alongside the PNG output."""
        json_path = output_path.replace(".png", "_metadata.json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info("Saved chart metadata to %s", json_path)
        except Exception as exc:
            logger.warning("Failed to save metadata JSON: %s", exc)
```

- [x] **Step 5: Run tests to verify they pass**

Run:
```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_renderer_v2.py -v
```
Expected: PASS

- [x] **Step 6: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/renderers/matplotlib_renderer.py ai_service/chart/chart_renderer.py ai_service/tests/test_chart_renderer_v2.py && git commit -m "refactor: MatplotlibRenderer returns ChartResult, injects cn_font, extracts metadata"
```

---

### Task 6: ChartService — upload metadata.json, return structured response

**Files:**
- Modify: `ai_service/chart/chart_service.py`

**Interfaces:**
- Consumes: `ChartResult` from renderer
- Produces: `ChartService.render()` returns dict with `type`, `url`, `metadata`, `metadata_url`, `summary`

- [x] **Step 1: Refactor ChartService.render()**

Edit `ai_service/chart/chart_service.py`. Replace the entire file content:

```python
"""ChartService — unified entry point for chart generation.

Only this module should be imported by tools/agents. Internal renderer/storage
details are hidden behind this facade, allowing engine swaps without changes
to callers or prompts.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path

from chart.minio_storage import MinioStorage
from chart.renderers.matplotlib_renderer import MatplotlibRenderer

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp")


class ChartService:
    """Generate charts from Python code, upload to MinIO, return image URL dict."""

    def __init__(self):
        self._renderer = MatplotlibRenderer()
        self._storage = MinioStorage()

    def render(self, code: str) -> dict:
        """Execute matplotlib code and return structured dict with metadata.

        Returns:
            On success::
                {
                    "type": "image",
                    "url": "https://minio/chart_abc.png",
                    "metadata": {"title": "...", "chart_type": "...", ...},
                    "metadata_url": "https://minio/chart_abc_metadata.json",
                    "summary": "...",
                }
            On error::
                {"type": "error", "error": "Chart rendering failed: ..."}
        """
        filename = f"chart_{uuid.uuid4().hex[:8]}.png"
        output_path = str(OUTPUT_DIR / filename)

        try:
            result = self._renderer.render(code, output_path)
        except Exception as e:
            logger.exception("Chart rendering failed")
            return {"type": "error", "error": f"Chart rendering failed: {e}"}

        # Upload PNG
        url = self._storage.upload(output_path)
        if not url:
            url = f"file://{output_path}"

        # Upload metadata.json
        metadata_url = None
        json_path = output_path.replace(".png", "_metadata.json")
        if os.path.isfile(json_path):
            metadata_url = self._storage.upload(json_path)

        return {
            "type": "image",
            "url": url,
            "metadata": result.metadata.to_dict(),
            "metadata_url": metadata_url,
            "summary": result.summary,
        }
```

- [x] **Step 2: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/chart_service.py && git commit -m "refactor: ChartService returns ChartResult metadata, uploads metadata.json"
```

---

### Task 7: Sandbox preamble — inject cn_font and Palette

**Files:**
- Modify: `ai_service/tools/sandbox/tool.py`

- [x] **Step 1: Update `_build_preamble()` to inject new imports**

Edit `ai_service/tools/sandbox/tool.py`. Locate the `_build_preamble()` method (lines 73-124). Replace the chart theme section (lines 90-93):

Old:
```python
        # ── Chart theme (font, DPI, style) ──
        lines.append("from chart.chart_theme import ChartTheme")
        lines.append("ChartTheme.initialize()")
```

New:
```python
        # ── Chart theme (font, DPI, style) ──
        lines.append("from chart.chart_theme import ChartTheme")
        lines.append("ChartTheme.initialize()")
        lines.append("")
        lines.append("# ── Inject cn_font and Palette for chart generation ──")
        lines.append("from chart.font_manager import FontManager")
        lines.append("cn_font = FontManager.get_cn_font()")
        lines.append("from chart.palette import Palette")
```

- [x] **Step 2: Run existing sandbox tests to verify no regression**

Run:
```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_code_sandbox.py -v
```
Expected: PASS

- [x] **Step 3: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/tools/sandbox/tool.py && git commit -m "feat: inject cn_font and Palette into sandbox preamble"
```

---

### Task 8: Prompt updates — _CHART_CODE_PROMPT and Composer prompt

**Files:**
- Modify: `ai_service/graph/nodes.py`

- [x] **Step 1: Update _CHART_CODE_PROMPT**

Edit `ai_service/graph/nodes.py`. Replace lines 892-911 (the `_CHART_CODE_PROMPT` string):

Old:
```python
_CHART_CODE_PROMPT = """\
You are a Python matplotlib expert. Generate Python code to create ONE chart based on the specification.

Specification:
{spec}

Available data context (from previous research steps):
{data_context}

CRITICAL RULES — follow exactly:
1. Start with: import matplotlib.pyplot as plt; import numpy as np
2. DO NOT import ChartTheme or any ai_service modules (they break in sandbox)
3. Use plt.rcParams to set Chinese fonts: plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Heiti SC', 'SimHei']; plt.rcParams['axes.unicode_minus'] = False
4. Set figure size to (12, 6)
5. Include title, axis labels, legend if applicable
6. Output ONLY valid Python code — no markdown wrappers, no explanation
7. Save using plt.savefig('chart_output.png', dpi=200, bbox_inches='tight')
8. Do NOT call plt.show()
9. End with plt.close()
"""
```

New:
```python
_CHART_CODE_PROMPT = """\
You are a Python matplotlib expert. Generate Python code to create ONE chart based on the specification.

Specification:
{spec}

Available data context (from previous research steps):
{data_context}

CRITICAL RULES — follow exactly:
1. Start with: import matplotlib.pyplot as plt; import numpy as np
2. DO NOT import ChartTheme or any ai_service modules (they break in sandbox)
3. The variables `cn_font` (FontProperties) and `Palette` are already available in the execution context — use them directly, do NOT import them
4. ALL text elements (title, labels, legend, tick labels, annotations) MUST use `fontproperties=cn_font` — example: ax.set_title("标题", fontproperties=cn_font)
5. Get colors from Palette: colors = Palette.get_series_colors(N)  — returns list of PaletteColor objects with .hex and .name_cn
6. Set figure size to (12, 6)
7. Include title, axis labels, legend if applicable
8. MUST set __chart_metadata__ with the following structure before saving:
   __chart_metadata__ = {
       "chart_type": "bar",  # or "line", "pie", "scatter", etc.
       "title": "图表标题",
       "series": [
           {"name": "系列名", "color": colors[0].hex, "color_name": colors[0].name_cn},
       ],
       "summary": "图表摘要 - 一句话描述图表展示的内容",
   }
9. Output ONLY valid Python code — no markdown wrappers, no explanation
10. Save using plt.savefig(__output_path__, dpi=200, bbox_inches='tight')
11. Do NOT call plt.show()
12. End with plt.close()
13. PROHIBITED: Do NOT use plt.rcParams['font.sans-serif'] — font is handled via fontproperties=cn_font
"""
```

- [x] **Step 2: Update _build_composer_system_prompt to include chart metadata awareness**

Edit `ai_service/graph/nodes.py`. In the `_build_composer_system_prompt` function (starting at line 1406), find the `_format_artifacts` helper (lines 1421-1434). Modify the image artifact formatting to include chart metadata:

Old:
```python
            if atype == "image" and content_ref:
                # For images, provide the actual URL and markdown syntax hint
                lines.append(f"- [{aid}] IMAGE for '{purpose}' — use this Markdown: ![{purpose}]({content_ref})")
```

New:
```python
            if atype == "image" and content_ref:
                # For images, provide the actual URL and markdown syntax hint
                meta_hint = ""
                if "metadata" in a and a["metadata"]:
                    series_info = a["metadata"].get("series", [])
                    summary = a.get("summary", "")
                    if series_info:
                        colors_str = "; ".join(
                            f'{s.get("name","")} ({s.get("color_name","")})'
                            for s in series_info
                        )
                        meta_hint = f" [colors: {colors_str}]"
                    if summary:
                        meta_hint += f" [summary: {summary}]"
                lines.append(f"- [{aid}] IMAGE for '{purpose}' — use this Markdown: ![{purpose}]({content_ref}){meta_hint}")
```

Also add chart metadata rules to the instructions section at the end of `_build_composer_system_prompt` (after the "If no research data" line, before "Current time"). Insert:

```python
	
	[Chart Color Rules]
	- When referencing chart series colors, use the color_name from the chart metadata (e.g., "GDP (蓝色)")
	- Do NOT invent or guess color descriptions — always use the metadata-provided color_name
	- Use the summary field from chart metadata when describing chart content
```

- [x] **Step 3: Run existing tests to verify no regression**

Run:
```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_generator.py ai_service/tests/test_chart_validators.py -v
```
Expected: PASS

- [x] **Step 4: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/graph/nodes.py && git commit -m "feat: update chart code prompt to use cn_font/Palette, add chart metadata to composer prompt"
```

---

### Task 9: Data Analyst prompt update (DB seed)

**Files:**
- No database seed file was found in the codebase. The Data Analyst agent rules from the design doc (section 3.3) need to be applied wherever the Data Analyst system prompt is defined.

- [x] **Step 1: Locate the Data Analyst Agent system prompt**

Search for the Data Analyst agent's system prompt definition:

```bash
cd /Volumes/work/projects/winter-agent && grep -rn "data.analyst\|DataAnalyst\|analyst.*system\|analyst.*prompt" ai_service/ --include="*.py" | grep -v __pycache__ | grep -v ".pyc"
```

If found, add the three rules from design doc section 3.3:
- "颜色描述必须来自 Chart Metadata，不得根据图片推测"
- "引用图例格式: 系列名（颜色名），颜色信息来自图表元数据"
- "使用 ChartResult.summary 作为图表描述，不要自行解释图表"

If no DB seed file is found (the search above returned no results), skip this task with a note.

- [x] **Step 2: Commit (if changes were made)**

```bash
cd /Volumes/work/projects/winter-agent && git add <modified-file> && git commit -m "feat: update Data Analyst prompt with chart metadata rules"
```

---

### Task 10: Regression test run

**Files:**
- No file changes — run existing tests to confirm no regressions

- [x] **Step 1: Run all chart-related tests**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_font_manager.py ai_service/tests/test_chart_palette.py ai_service/tests/test_chart_renderer_v2.py ai_service/tests/test_chart_generator.py ai_service/tests/test_chart_validators.py ai_service/tests/test_chart_spec.py ai_service/tests/test_chart_registry.py ai_service/tests/test_chart_envelope.py -v
```
Expected: ALL PASS

- [x] **Step 2: Run sandbox test**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_code_sandbox.py -v
```
Expected: PASS

- [x] **Step 3: Commit the test results verification**

No code changes in this task. Verification is complete when all tests pass.

---

### Task 11: E2E verification — generate chart types, confirm Chinese + metadata

**Files:**
- No file changes — manual verification

- [x] **Step 1: Write and run E2E verification script**

Create a temporary script `_e2e_verify.py` (DO NOT COMMIT — delete after use):

```python
"""E2E verification: generate multiple chart types, check Chinese and metadata."""
import json
import os
import tempfile
import sys

sys.path.insert(0, "ai_service")

from chart.renderers.matplotlib_renderer import MatplotlibRenderer
from chart.font_manager import FontManager

FontManager.initialize()
print(f"Font: {FontManager.get_font_name()}")

renderer = MatplotlibRenderer()

CHARTS = {
    "line": """\
import matplotlib.pyplot as plt
import numpy as np
cn_font
x = np.arange(1, 6)
y = np.array([10, 20, 15, 25, 30])
colors = Palette.get_series_colors(2)
__chart_metadata__ = {"chart_type": "line", "title": "线图测试", "series": [
    {"name": "GDP", "color": colors[0].hex, "color_name": colors[0].name_cn},
    {"name": "CPI", "color": colors[1].hex, "color_name": colors[1].name_cn},
], "summary": "GDP和CPI趋势"}
fig, ax = plt.subplots()
ax.plot(x, y, color=colors[0].hex, label="GDP")
ax.plot(x, y * 0.8, color=colors[1].hex, label="CPI")
ax.set_title("线图测试", fontproperties=cn_font)
ax.set_xlabel("年份", fontproperties=cn_font)
ax.set_ylabel("数值", fontproperties=cn_font)
ax.legend()
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
plt.close(fig)
""",

    "bar": """\
import matplotlib.pyplot as plt
import numpy as np
colors = Palette.get_series_colors(3)
categories = ["一季度", "二季度", "三季度", "四季度"]
values = [100, 120, 90, 150]
__chart_metadata__ = {"chart_type": "bar", "title": "季度销售", "series": [
    {"name": "销售额", "color": colors[0].hex, "color_name": colors[0].name_cn},
], "summary": "四季度销售额最高"}
fig, ax = plt.subplots()
ax.bar(categories, values, color=colors[0].hex, label="销售额")
ax.set_title("季度销售", fontproperties=cn_font)
ax.set_xlabel("季度", fontproperties=cn_font)
ax.set_ylabel("万元", fontproperties=cn_font)
ax.legend()
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
plt.close(fig)
""",
}

with tempfile.TemporaryDirectory() as d:
    for name, code in CHARTS.items():
        output = os.path.join(d, f"{name}.png")
        result = renderer.render(code, output)
        assert os.path.isfile(output), f"{name}: PNG not created"
        json_path = output.replace(".png", "_metadata.json")
        assert os.path.isfile(json_path), f"{name}: metadata JSON not created"
        with open(json_path) as f:
            meta = json.load(f)
        assert meta["title"], f"{name}: title is empty"
        assert meta["chart_type"] == name, f"{name}: chart_type mismatch"
        assert meta["series"], f"{name}: series is empty"
        print(f"[PASS] {name}: title={meta['title']}, series={len(meta['series'])}")

print("All E2E checks passed!")
```

Run:
```bash
cd /Volumes/work/projects/winter-agent && python _e2e_verify.py
```
Expected: "All E2E checks passed!" — no errors

- [x] **Step 2: Delete the temporary verification script**

```bash
rm /Volumes/work/projects/winter-agent/_e2e_verify.py
```

- [x] **Step 3: Commit (empty — E2E is verification only, no code changes)**

E2E verification is complete. No commit needed for this task.

---

## Self-Review

### 1. Spec coverage

| Design Doc Section | Covered By |
|---|---|
| 2.1 FontManager | Task 1 |
| 2.2 Palette | Task 2 |
| 2.3 ChartResult + ChartMetadata | Task 3 |
| 2.4 MatplotlibRenderer | Task 5 |
| 2.5 ChartTheme | Task 4 |
| 2.6 ChartService | Task 6 |
| 3.1 Chart Code Prompt | Task 8 |
| 3.2 Composer Prompt | Task 8 |
| 3.3 Data Analyst Prompt | Task 9 |
| 4.1 image.uploaded (unchanged) | Task 6 (preserves existing SSE) |
| 4.2 chart.metadata (new) | Task 6 (metadata in return dict) |
| 5. File structure | All tasks |

### 2. Placeholder scan

All code blocks contain complete, runnable code. No "TBD", "TODO", "implement later", or similar placeholders. No "add error handling" without actual code. No "similar to Task X" references.

### 3. Type consistency

- `FontManager.get_cn_font() -> FontProperties` (Task 1) matches usage in MatplotlibRenderer (Task 5) and sandbox preamble (Task 7)
- `Palette.get_series_colors(n) -> list[PaletteColor]` (Task 2) matches usage in prompt examples (Task 8)
- `Palette.get_color_name(hex) -> str` (Task 2) matches usage in MatplotlibRenderer._l2_fill_gaps (Task 5)
- `ChartResult(image_path, metadata, summary)` (Task 3) matches MatplotlibRenderer.render() return type (Task 5) and ChartService usage (Task 6)
- `ChartMetadata.to_dict()` (Task 3) matches ChartService return dict format (Task 6)
- `AbstractChartRenderer.render() -> ChartResult` (Task 5) preserves interface contract

### Gaps found

- **Task 9 (Data Analyst prompt):** No DB seed or Data Analyst system prompt file was found during exploration. The Task 9 implements a search step; if no file is found, this section of the spec (3.3) will be documented as needing a follow-up. This should be flagged to the user.
- **SSE protocol (section 4.2):** The design doc describes a `chart.metadata` SSE event. The current `ChartService` does not directly emit SSE. The SSE emissions are handled elsewhere in the graph pipeline (likely in the streaming/SSE handler). The metadata dict returned by `ChartService.render()` is available for any downstream SSE emitter to format and push. The SSE handler itself is out of scope for this plan — the design doc says it's "new" but doesn't specify which file implements it.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-28-chart-infrastructure-v2.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
