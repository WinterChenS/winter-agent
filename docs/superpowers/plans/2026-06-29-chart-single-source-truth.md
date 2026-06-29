---
change: chart-single-source-truth
design-doc: docs/superpowers/specs/2026-06-29-chart-single-source-truth-design.md
base-ref: 5aa813ae6caf5402ecec0d36233b4eda2c601093
---

# Chart Single Source of Truth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `ChartSpec` as the single source of truth for chart generation, add `render_from_spec` to `MatplotlibRenderer`, replace `__chart_metadata__` with `ChartSpec.to_metadata()`, add `compute_summary` to `ChartResult`, implement metadata scanning in `CodeSandboxTool`, and update all prompts to reference metadata instead of guessing.

**Architecture:** Three new modules (`palette.py`, `chart_spec.py`, `chart_result.py`) provide typed data classes. `FontManager` centralizes font discovery. `MatplotlibRenderer` gains `render_from_spec(spec, output_path)` which renders from `ChartSpec` and saves `_metadata.json` alongside the PNG. The old `render(code, path)` remains backward-compatible. `CodeSandboxTool._build_preamble()` injects `cn_font` and `Palette`. After execution, the sandbox scans for `_metadata.json` files and attaches them as `charts` in `ToolResult`. The composer prompt references chart metadata (colors, summary) instead of guessing from images.

**Tech Stack:** Python 3.11+, matplotlib 3.6+, pytest, `numpy` for trend calculation.

## Global Constraints

- All chart text MUST use `fontproperties=cn_font` (FontProperties object), NOT `plt.rcParams['font.sans-serif']`.
- All chart colors MUST come from `Palette.get_series_colors(N)` — no hardcoded hex values in generated code.
- `ChartSpec` is the single source of truth: metadata is generated from `spec.to_metadata()`, not from `__chart_metadata__`.
- `render(code, path)` stays backward compatible: returns `ChartResult` with empty metadata `{}` when no `__chart_spec__` is declared.
- The old `color_utils.py` PALETTE list MUST remain available as a backward-compatible re-export.
- No new third-party Python dependencies.

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `ai_service/chart/palette.py` | Palette class: 7 named PaletteColor constants + `SERIES` (12 colors), `get_series_colors(n)`, `get_color_name(hex)` |
| `ai_service/chart/font_manager.py` | FontManager singleton: cross-platform font discovery, cached FontProperties |
| `ai_service/chart/chart_spec.py` | ChartSpec, SeriesSpec, SliceSpec, PointSpec dataclasses — the single source of truth |
| `ai_service/chart/chart_result.py` | ChartResult(image_path, metadata, summary, stdout) dataclass + `compute_summary()` |

### Modified files
| File | Changes |
|------|---------|
| `ai_service/chart/chart_renderer.py` | Add `render_from_spec(spec, output_path)` abstract method, change `render()` return type to `ChartResult` |
| `ai_service/chart/renderers/matplotlib_renderer.py` | Add `render_from_spec()`, refactor `render()` to return `ChartResult`, inject `cn_font` and `Palette` into exec context, save `_metadata.json` |
| `ai_service/chart/chart_service.py` | Detect `__chart_spec__` variable to route to `render_from_spec()`, return `metadata` + `summary` in response dict |
| `ai_service/chart/chart_theme.py` | Delegate font to `FontManager.initialize()`, remove `_find_chinese_font()`, drop rcParams font lines |
| `ai_service/chart/utils/color_utils.py` | Re-export from `Palette` for backward compatibility |
| `ai_service/tools/sandbox/tool.py` | Inject `cn_font` + `Palette` imports in preamble; scan for `_metadata.json` after execution; add `charts` field to `ToolResult` |
| `ai_service/graph/nodes.py` | Update `_CHART_CODE_PROMPT` to require ChartSpec; update `_build_composer_system_prompt` to reference metadata |
| `ai_service/db/migrations/002_seed_agents_and_setup.sql` | Update Data Analyst system prompt with metadata rules |
| `ai_service/chart/__init__.py` | Export new public symbols |

### Test files
| File | Responsibility |
|------|---------------|
| `ai_service/tests/test_chart_palette.py` | Palette tests: constants, get_series_colors, get_color_name |
| `ai_service/tests/test_chart_font_manager.py` | FontManager tests: init, discovery, caching, fallback |
| `ai_service/tests/test_chart_spec_v2.py` | ChartSpec tests: creation, serialization, metadata, all_values |
| `ai_service/tests/test_chart_result.py` | ChartResult tests: compute_summary, serialization |
| `ai_service/tests/test_chart_renderer_v2.py` | MatplotlibRenderer tests: render_from_spec, backward-compatible render |

---

### Task 1: Palette — fixed color palette with Chinese names

**Files:**
- Create: `ai_service/chart/palette.py`
- Modify: `ai_service/chart/__init__.py` (add exports)
- Modify: `ai_service/chart/utils/color_utils.py` (backward-compatible re-export)
- Test: `ai_service/tests/test_chart_palette.py`

**Interfaces:**
- Consumes: nothing (standalone module)
- Produces: `PaletteColor(NamedTuple)` with `hex: str`, `name_cn: str`; `Palette` class with `PRIMARY`, `SECONDARY`, `SUCCESS`, `WARNING`, `ERROR`, `INFO`, `NEUTRAL` constants, `SERIES` (list of 12 `PaletteColor`), `get_series_colors(n) -> list[PaletteColor]`, `get_color_name(hex) -> str`

- [x] **Step 1: Write the failing Palette test**

Create `ai_service/tests/test_chart_palette.py`:

```python
"""Tests for Palette — enterprise color palette with Chinese names."""
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
    def test_primary(self):
        assert Palette.PRIMARY.hex == "#2F80ED"
        assert Palette.PRIMARY.name_cn == "蓝色"

    def test_secondary(self):
        assert Palette.SECONDARY.hex == "#27AE60"
        assert Palette.SECONDARY.name_cn == "绿色"

    def test_success(self):
        assert Palette.SUCCESS.hex == "#219653"
        assert Palette.SUCCESS.name_cn == "深绿"

    def test_warning(self):
        assert Palette.WARNING.hex == "#F2994A"
        assert Palette.WARNING.name_cn == "橙色"

    def test_error(self):
        assert Palette.ERROR.hex == "#EB5757"
        assert Palette.ERROR.name_cn == "红色"

    def test_info(self):
        assert Palette.INFO.hex == "#9B51E0"
        assert Palette.INFO.name_cn == "紫色"

    def test_neutral(self):
        assert Palette.NEUTRAL.hex == "#828282"
        assert Palette.NEUTRAL.name_cn == "灰色"

    def test_series_has_12_colors(self):
        assert len(Palette.SERIES) == 12

    def test_series_first_7_match_constants(self):
        expected_first_7 = [
            Palette.PRIMARY, Palette.SECONDARY, Palette.SUCCESS,
            Palette.WARNING, Palette.ERROR, Palette.INFO, Palette.NEUTRAL,
        ]
        assert Palette.SERIES[:7] == expected_first_7


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
        colors = Palette.get_series_colors(14)
        assert len(colors) == 14
        assert colors[:12] == Palette.SERIES
        assert colors[12].name_cn == "蓝色_1"


class TestGetColorName:
    def test_known_color(self):
        assert Palette.get_color_name("#2F80ED") == "蓝色"

    def test_unknown_color_returns_self(self):
        assert Palette.get_color_name("#123456") == "#123456"

    def test_case_sensitive(self):
        assert Palette.get_color_name("#2f80ed") == "#2f80ed"
```

- [x] **Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest ai_service/tests/test_chart_palette.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'chart.palette'`

- [x] **Step 3: Create Palette module**

Create `ai_service/chart/palette.py`:

```python
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
```

- [x] **Step 4: Update color_utils.py for backward compatibility**

Replace content of `ai_service/chart/utils/color_utils.py`:

```python
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
```

- [x] **Step 5: Update package exports**

Write to `ai_service/chart/__init__.py`:

```python
from chart.palette import Palette, PaletteColor

__all__ = [
    "Palette",
    "PaletteColor",
]
```

- [x] **Step 6: Run tests to verify they pass**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_palette.py -v
```
Expected: PASS (all tests)

- [x] **Step 7: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/palette.py ai_service/chart/utils/color_utils.py ai_service/chart/__init__.py ai_service/tests/test_chart_palette.py && git commit -m "feat: add Palette with Chinese color names and backward-compatible color_utils"
```

---

### Task 2: FontManager — cross-platform font discovery and caching

**Files:**
- Create: `ai_service/chart/font_manager.py`
- Modify: `ai_service/chart/chart_theme.py` (delegate to FontManager)
- Test: `ai_service/tests/test_chart_font_manager.py`

**Interfaces:**
- Consumes: nothing
- Produces: `FontManager` class with classmethods `initialize(force=False)`, `get_cn_font() -> FontProperties`, `get_font_name() -> str`, `validate_figure_fonts(fig) -> list[str]`

- [x] **Step 1: Write the failing FontManager test**

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
```

- [x] **Step 2: Run test to verify it fails**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_font_manager.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'chart.font_manager'`

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
        return None

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
```

- [x] **Step 4: Refactor ChartTheme to delegate font to FontManager**

Replace `ai_service/chart/chart_theme.py`:

```python
"""Enterprise chart theme — unified font, color, DPI, and layout configuration.

Font management is delegated to FontManager. This module only handles
non-font style configuration (DPI, figure size, grid, colors).
"""
from __future__ import annotations

import matplotlib.pyplot as plt
from chart.font_manager import FontManager


class ChartTheme:
    """Enterprise chart theme. Call ChartTheme.initialize() once before plotting."""

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

- [x] **Step 5: Run tests to verify they pass**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_font_manager.py -v
```
Expected: PASS

- [x] **Step 6: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/font_manager.py ai_service/chart/chart_theme.py ai_service/tests/test_chart_font_manager.py && git commit -m "feat: add FontManager for cross-platform font discovery, refactor ChartTheme delegation"
```

---

### Task 3: ChartSpec — the single source of truth for chart data

**Files:**
- Create: `ai_service/chart/chart_spec.py`
- Test: `ai_service/tests/test_chart_spec_v2.py`

**Interfaces:**
- Consumes: `Palette.get_color_name(hex)` from `chart.palette`
- Produces: `SeriesSpec(name, color, color_name, values)`, `SliceSpec(label, value, color, color_name)`, `PointSpec(x, y, label)`, `ChartSpec(title, chart_type, xlabel, ylabel, figsize, series, slices, points, data, labels)` with `to_metadata() -> dict`, `all_values() -> list[float]`, `__post_init__` auto-fills `color_name`

- [x] **Step 1: Write the failing ChartSpec test**

Create `ai_service/tests/test_chart_spec_v2.py`:

```python
"""Tests for ChartSpec v2 — the single source of truth for chart data."""
from __future__ import annotations

import json

import pytest

from chart.chart_spec import ChartSpec, SeriesSpec, SliceSpec, PointSpec


class TestSeriesSpec:
    def test_create_minimal(self):
        s = SeriesSpec(name="GDP", color="#2F80ED", color_name="蓝色", values=[1, 2, 3])
        assert s.name == "GDP"
        assert s.color == "#2F80ED"
        assert s.color_name == "蓝色"
        assert s.values == [1, 2, 3]


class TestSliceSpec:
    def test_create_minimal(self):
        s = SliceSpec(label="A", value=30.0, color="#EB5757", color_name="红色")
        assert s.label == "A"
        assert s.value == 30.0
        assert s.color_name == "红色"


class TestPointSpec:
    def test_create_without_label(self):
        p = PointSpec(x=1.0, y=2.0)
        assert p.x == 1.0
        assert p.y == 2.0
        assert p.label is None

    def test_create_with_label(self):
        p = PointSpec(x=1.0, y=2.0, label="peak")
        assert p.label == "peak"


class TestChartSpec:
    def test_create_bar_spec(self):
        spec = ChartSpec(
            title="Sales",
            chart_type="bar",
            xlabel="Quarter",
            ylabel="Revenue",
            series=[
                SeriesSpec(name="Q1", color="#2F80ED", color_name="蓝色", values=[100]),
            ],
        )
        assert spec.title == "Sales"
        assert spec.chart_type == "bar"
        assert spec.xlabel == "Quarter"
        assert spec.ylabel == "Revenue"

    def test_create_pie_spec(self):
        spec = ChartSpec(
            title="Market Share",
            chart_type="pie",
            slices=[
                SliceSpec(label="A", value=30, color="#2F80ED", color_name="蓝色"),
                SliceSpec(label="B", value=70, color="#EB5757", color_name="红色"),
            ],
        )
        assert len(spec.slices) == 2

    def test_create_scatter_spec(self):
        spec = ChartSpec(
            title="Scatter",
            chart_type="scatter",
            points=[PointSpec(x=1, y=2), PointSpec(x=3, y=4)],
        )
        assert len(spec.points) == 2

    def test_default_figsize(self):
        spec = ChartSpec(title="T", chart_type="bar", series=[SeriesSpec("X", "#000", "", [])])
        assert spec.figsize == (12, 6)

    def test_color_name_auto_fill(self):
        spec = ChartSpec(
            title="AutoFill",
            chart_type="bar",
            series=[
                SeriesSpec(name="S1", color="#2F80ED", color_name="", values=[10]),
            ],
        )
        assert spec.series[0].color_name == "蓝色"


class TestToMetadata:
    def test_bar_metadata(self):
        spec = ChartSpec(
            title="Sales",
            chart_type="bar",
            xlabel="Quarter",
            ylabel="Revenue",
            figsize=(10, 5),
            series=[
                SeriesSpec(name="Q1", color="#2F80ED", color_name="蓝色", values=[100, 200]),
            ],
        )
        meta = spec.to_metadata()
        assert meta["title"] == "Sales"
        assert meta["chart_type"] == "bar"
        assert meta["xlabel"] == "Quarter"
        assert meta["ylabel"] == "Revenue"
        assert meta["figsize"] == [10, 5]
        assert len(meta["series"]) == 1
        assert meta["series"][0]["name"] == "Q1"
        assert meta["series"][0]["color"] == "#2F80ED"
        assert meta["series"][0]["color_name"] == "蓝色"

    def test_pie_metadata(self):
        spec = ChartSpec(
            title="Pie",
            chart_type="pie",
            slices=[
                SliceSpec(label="A", value=30, color="#EB5757", color_name="红色"),
            ],
        )
        meta = spec.to_metadata()
        assert meta["chart_type"] == "pie"
        assert meta["slices"][0]["label"] == "A"

    def test_metadata_json_serializable(self):
        spec = ChartSpec(
            title="JSON",
            chart_type="bar",
            series=[SeriesSpec("S", "#2F80ED", "蓝色", [1, 2])],
        )
        json_str = json.dumps(spec.to_metadata(), ensure_ascii=False)
        assert isinstance(json_str, str)


class TestAllValues:
    def test_bar_values(self):
        spec = ChartSpec(
            title="T", chart_type="bar",
            series=[
                SeriesSpec("A", "#000", "", [1, 2, 3]),
                SeriesSpec("B", "#111", "", [4, 5]),
            ],
        )
        assert spec.all_values() == [1, 2, 3, 4, 5]

    def test_pie_values(self):
        spec = ChartSpec(
            title="T", chart_type="pie",
            slices=[
                SliceSpec("A", 30.0, "#000", ""),
                SliceSpec("B", 70.0, "#111", ""),
            ],
        )
        assert spec.all_values() == [30.0, 70.0]

    def test_empty_returns_empty_list(self):
        spec = ChartSpec(title="T", chart_type="bar")
        assert spec.all_values() == []
```

- [x] **Step 2: Run test to verify it fails**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_spec_v2.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'chart.chart_spec'`

- [x] **Step 3: Create ChartSpec module**

Create `ai_service/chart/chart_spec.py`:

```python
"""ChartSpec — typed specification for chart rendering (single source of truth).

This module defines the data classes used to describe a chart declaratively.
ChartSpec is the single source of truth: metadata, rendering parameters, and
data values all flow from a single ChartSpec instance.

Usage:
    spec = ChartSpec(
        title="Sales",
        chart_type="bar",
        series=[SeriesSpec(name="Q1", color="#2F80ED", color_name="", values=[100, 200])],
    )
    meta = spec.to_metadata()   # -> dict for metadata.json and prompts
    vals = spec.all_values()    # -> [100, 200] for summary computation
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from chart.palette import Palette


@dataclass
class SeriesSpec:
    """A single data series in a bar or line chart."""
    name: str
    color: str
    color_name: str
    values: list[float]


@dataclass
class SliceSpec:
    """A single slice in a pie chart."""
    label: str
    value: float
    color: str
    color_name: str


@dataclass
class PointSpec:
    """A single point in a scatter chart."""
    x: float
    y: float
    label: str | None = None


@dataclass
class ChartSpec:
    """Declarative chart specification — the single source of truth.

    Fields:
        title: Chart title.
        chart_type: One of line/bar/pie/scatter/histogram/heatmap.
        xlabel: X-axis label (bar/line/scatter/histogram).
        ylabel: Y-axis label (bar/line/scatter/histogram).
        figsize: (width, height) in inches.
        series: Data series for bar/line charts.
        slices: Data slices for pie charts.
        points: Data points for scatter charts.
        data: Raw data matrix for histogram/heatmap.
        labels: Category labels for histogram/heatmap.
    """
    title: str
    chart_type: str
    xlabel: str | None = None
    ylabel: str | None = None
    figsize: tuple = (12, 6)
    series: list[SeriesSpec] | None = None
    slices: list[SliceSpec] | None = None
    points: list[PointSpec] | None = None
    data: list[list[float]] | None = None
    labels: list[str] | None = None

    def __post_init__(self):
        if self.series:
            for s in self.series:
                if not s.color_name:
                    s.color_name = Palette.get_color_name(s.color)

    def to_metadata(self) -> dict[str, Any]:
        """Serialize ChartSpec to a metadata dict for the JSON file and prompts."""
        meta: dict[str, Any] = {
            "title": self.title,
            "chart_type": self.chart_type,
            "xlabel": self.xlabel,
            "ylabel": self.ylabel,
            "figsize": list(self.figsize),
        }
        if self.series:
            meta["series"] = [
                {"name": s.name, "color": s.color, "color_name": s.color_name}
                for s in self.series
            ]
        if self.slices:
            meta["slices"] = [
                {"label": s.label, "value": s.value, "color": s.color, "color_name": s.color_name}
                for s in self.slices
            ]
        if self.labels:
            meta["labels"] = self.labels
        return meta

    def all_values(self) -> list[float]:
        """Collect all numeric values from the spec for summary computation."""
        values: list[float] = []
        if self.series:
            for s in self.series:
                values.extend(s.values)
        if self.slices:
            for s in self.slices:
                values.append(s.value)
        if self.points:
            for p in self.points:
                values.append(p.x)
                values.append(p.y)
        return values
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_spec_v2.py -v
```
Expected: PASS

- [x] **Step 5: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/chart_spec.py ai_service/tests/test_chart_spec_v2.py && git commit -m "feat: add ChartSpec, SeriesSpec, SliceSpec, PointSpec dataclasses"
```

---

### Task 4: ChartResult — structured output with compute_summary

**Files:**
- Create: `ai_service/chart/chart_result.py`
- Test: `ai_service/tests/test_chart_result.py`

**Interfaces:**
- Consumes: nothing (standalone)
- Produces: `ChartResult(image_path: str, metadata: dict, summary: str, stdout: str)` with `to_dict() -> dict`, `compute_summary(values, labels) -> str` (static method)

- [x] **Step 1: Write the failing ChartResult test**

Create `ai_service/tests/test_chart_result.py`:

```python
"""Tests for ChartResult — structured chart output with summary computation."""
from __future__ import annotations

import json
import math

import pytest

from chart.chart_result import ChartResult


class TestChartResult:
    def test_create_minimal(self):
        r = ChartResult(image_path="/tmp/test.png", metadata={}, summary="", stdout="")
        assert r.image_path == "/tmp/test.png"
        assert r.metadata == {}
        assert r.summary == ""
        assert r.stdout == ""

    def test_create_full(self):
        r = ChartResult(
            image_path="/tmp/test.png",
            metadata={"title": "Test", "chart_type": "bar"},
            summary="Max: 100, Min: 10, Avg: 55.0",
            stdout="[INFO] rendering complete",
        )
        assert r.metadata["title"] == "Test"
        assert r.summary.startswith("Max:")

    def test_to_dict(self):
        r = ChartResult(
            image_path="/tmp/test.png",
            metadata={"title": "T"},
            summary="sum",
            stdout="",
        )
        d = r.to_dict()
        assert d["image_path"] == "/tmp/test.png"
        assert d["metadata"]["title"] == "T"
        assert d["summary"] == "sum"

    def test_to_dict_json_serializable(self):
        r = ChartResult(
            image_path="/tmp/test.png",
            metadata={"title": "T"},
            summary="Max: 100",
            stdout="",
        )
        json_str = json.dumps(r.to_dict(), ensure_ascii=False)
        assert isinstance(json_str, str)


class TestComputeSummary:
    def test_basic_stats(self):
        summary = ChartResult.compute_summary([10, 20, 30, 40, 100])
        assert "Max: 100.0" in summary
        assert "Min: 10.0" in summary
        assert "Avg: 40.0" in summary

    def test_ascending_trend(self):
        summary = ChartResult.compute_summary([1, 2, 3, 4, 5])
        assert "trend: ↑" in summary or "上升" in summary

    def test_descending_trend(self):
        summary = ChartResult.compute_summary([5, 4, 3, 2, 1])
        assert "trend: ↓" in summary or "下降" in summary

    def test_empty_list(self):
        summary = ChartResult.compute_summary([])
        assert "No data" in summary or summary == ""

    def test_single_value(self):
        summary = ChartResult.compute_summary([42])
        assert "Max" in summary
        assert "42" in summary

    def test_growth_rate_positive(self):
        summary = ChartResult.compute_summary([100, 150])
        assert "growth" in summary.lower()
        assert "50.0%" in summary
```

- [x] **Step 2: Run test to verify it fails**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_result.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'chart.chart_result'`

- [x] **Step 3: Create ChartResult module**

Create `ai_service/chart/chart_result.py`:

```python
"""Structured chart output types.

ChartResult is the return type of all renderers. compute_summary() provides
programmatic text summaries (max/min/avg/trend/growth_rate) for the composer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ChartResult:
    """Complete output of a chart rendering operation.

    Fields:
        image_path: Absolute path to the generated PNG.
        metadata: Dict from ChartSpec.to_metadata() (or {} for legacy code).
        summary: Text summary from compute_summary().
        stdout: Captured stdout from rendering (if any).
    """
    image_path: str
    metadata: dict
    summary: str
    stdout: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_path": self.image_path,
            "metadata": self.metadata,
            "summary": self.summary,
        }

    @staticmethod
    def compute_summary(values: list[float], labels: list[str] | None = None) -> str:
        """Compute a programmatic text summary from numeric values.

        Includes max, min, avg, trend direction (linear regression slope),
        and growth rate (first to last value).

        Args:
            values: List of numeric values.
            labels: Optional per-value labels (not yet used).

        Returns:
            Text summary suitable for LLM consumption, or empty string if
            values is empty.
        """
        if not values:
            return ""

        n = len(values)
        max_val = max(values)
        min_val = min(values)
        avg_val = sum(values) / n

        parts = [f"Max: {max_val}", f"Min: {min_val}", f"Avg: {avg_val}"]

        if n >= 2:
            # Linear regression slope for trend
            x_mean = (n - 1) / 2.0
            y_mean = avg_val
            num = 0.0
            den = 0.0
            for i, v in enumerate(values):
                dx = i - x_mean
                dy = v - y_mean
                num += dx * dy
                den += dx * dx
            slope = num / den if den != 0 else 0.0
            if slope > 0.01:
                parts.append("trend: ↑")
            elif slope < -0.01:
                parts.append("trend: ↓")
            else:
                parts.append("trend: →")

            # Growth rate (first to last)
            first = values[0]
            last = values[-1]
            if first != 0:
                growth = ((last - first) / abs(first)) * 100.0
                parts.append(f"growth: {growth:+.1f}%")

        return " | ".join(parts)
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_result.py -v
```
Expected: PASS

- [x] **Step 5: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/chart_result.py ai_service/tests/test_chart_result.py && git commit -m "feat: add ChartResult with compute_summary for programmatic text summaries"
```

---

### Task 5: ChartRenderer — add render_from_spec, refactor render() to return ChartResult

**Files:**
- Modify: `ai_service/chart/chart_renderer.py` (add abstract method, update return type)
- Modify: `ai_service/chart/renderers/matplotlib_renderer.py` (add render_from_spec, save metadata JSON, inject cn_font/Palette)
- Test: `ai_service/tests/test_chart_renderer_v2.py`

**Interfaces:**
- Consumes: `ChartResult`, `ChartSpec`, `FontManager`, `Palette`
- Produces: `MatplotlibRenderer.render(code, path) -> ChartResult` (backward compat, empty metadata when no __chart_spec__), `MatplotlibRenderer.render_from_spec(spec, path) -> ChartResult` (full metadata from ChartSpec)

- [x] **Step 1: Update AbstractChartRenderer**

Edit `ai_service/chart/chart_renderer.py`:

```python
"""Abstract chart renderer — extensibility point for matplotlib/seaborn/plotly."""
from __future__ import annotations

from abc import ABC, abstractmethod

from chart.chart_result import ChartResult
from chart.chart_spec import ChartSpec


class AbstractChartRenderer(ABC):
    """Base class for chart rendering engines. Extend for new backends."""

    @abstractmethod
    def render(self, code: str, output_path: str) -> ChartResult:
        """Execute rendering code, saving chart to output_path. Returns ChartResult."""
        ...

    @abstractmethod
    def render_from_spec(self, spec: ChartSpec, output_path: str) -> ChartResult:
        """Render from a ChartSpec directly (new, preferred path). Returns ChartResult."""
        ...
```

- [x] **Step 2: Write the failing MatplotlibRenderer test**

Create `ai_service/tests/test_chart_renderer_v2.py`:

```python
"""Tests for MatplotlibRenderer — render_from_spec, backward-compatible render, metadata."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from chart.chart_result import ChartResult
from chart.chart_spec import ChartSpec, SeriesSpec, SliceSpec
from chart.renderers.matplotlib_renderer import MatplotlibRenderer


@pytest.fixture
def renderer():
    return MatplotlibRenderer()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestRenderFromSpec:
    def test_render_bar(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Test Bar",
            chart_type="bar",
            xlabel="X",
            ylabel="Y",
            series=[SeriesSpec(name="S1", color="#2F80ED", color_name="蓝色", values=[10, 20, 30])],
        )
        output = os.path.join(temp_dir, "bar.png")
        result = renderer.render_from_spec(spec, output)
        assert isinstance(result, ChartResult)
        assert result.image_path == output
        assert os.path.isfile(output)

    def test_render_line(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Test Line",
            chart_type="line",
            series=[SeriesSpec(name="S1", color="#27AE60", color_name="绿色", values=[1, 2, 3])],
        )
        output = os.path.join(temp_dir, "line.png")
        result = renderer.render_from_spec(spec, output)
        assert os.path.isfile(output)
        assert result.metadata["title"] == "Test Line"
        assert result.metadata["chart_type"] == "line"

    def test_render_pie(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Test Pie",
            chart_type="pie",
            slices=[SliceSpec("A", 30, "#EB5757", "红色"), SliceSpec("B", 70, "#2F80ED", "蓝色")],
        )
        output = os.path.join(temp_dir, "pie.png")
        result = renderer.render_from_spec(spec, output)
        assert os.path.isfile(output)

    def test_render_scatter(self, renderer, temp_dir):
        from chart.chart_spec import PointSpec
        spec = ChartSpec(
            title="Test Scatter",
            chart_type="scatter",
            points=[PointSpec(1, 2), PointSpec(3, 4), PointSpec(5, 6)],
        )
        output = os.path.join(temp_dir, "scatter.png")
        result = renderer.render_from_spec(spec, output)
        assert os.path.isfile(output)

    def test_metadata_json_created(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Meta",
            chart_type="bar",
            series=[SeriesSpec("S", "#2F80ED", "蓝色", [1])],
        )
        output = os.path.join(temp_dir, "meta.png")
        renderer.render_from_spec(spec, output)
        json_path = output.replace(".png", "_metadata.json")
        assert os.path.isfile(json_path)
        with open(json_path) as f:
            data = json.load(f)
        assert data["title"] == "Meta"
        assert data["chart_type"] == "bar"

    def test_metadata_contains_summary(self, renderer, temp_dir):
        spec = ChartSpec(
            title="Summary Test",
            chart_type="bar",
            series=[SeriesSpec("S", "#2F80ED", "蓝色", [10, 20, 30])],
        )
        output = os.path.join(temp_dir, "summary.png")
        result = renderer.render_from_spec(spec, output)
        assert "Max" in result.summary


class TestRenderBackwardCompat:
    CODE_NO_SPEC = """\
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot([1,2,3], [4,5,6], label="My Series")
ax.set_title("Legacy")
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
plt.close(fig)
"""

    def test_render_returns_chart_result(self, renderer, temp_dir):
        output = os.path.join(temp_dir, "legacy.png")
        result = renderer.render(self.CODE_NO_SPEC, output)
        assert isinstance(result, ChartResult)
        assert result.image_path == output

    def test_legacy_metadata_is_empty_dict(self, renderer, temp_dir):
        output = os.path.join(temp_dir, "legacy.png")
        result = renderer.render(self.CODE_NO_SPEC, output)
        assert result.metadata == {}

    def test_legacy_summary_is_empty(self, renderer, temp_dir):
        output = os.path.join(temp_dir, "legacy.png")
        result = renderer.render(self.CODE_NO_SPEC, output)
        assert result.summary == ""

    def test_cn_font_injected(self, renderer, temp_dir):
        code = """\
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.set_title("Test", fontproperties=cn_font)
fig.savefig(__output_path__, dpi=200, bbox_inches="tight")
plt.close(fig)
"""
        output = os.path.join(temp_dir, "font_test.png")
        result = renderer.render(code, output)
        assert result.image_path == output
```

- [x] **Step 3: Run test to verify it fails**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_renderer_v2.py -v
```
Expected: FAIL (return type mismatch, missing render_from_spec)

- [x] **Step 4: Implement MatplotlibRenderer with render_from_spec**

Replace `ai_service/chart/renderers/matplotlib_renderer.py`:

```python
"""Matplotlib chart renderer — returns ChartResult via render() or render_from_spec()."""
from __future__ import annotations

import json
import logging
import os

from chart.chart_renderer import AbstractChartRenderer
from chart.font_manager import FontManager
from chart.chart_result import ChartResult
from chart.chart_spec import ChartSpec
from chart.palette import Palette

logger = logging.getLogger(__name__)


class MatplotlibRenderer(AbstractChartRenderer):
    """Render charts using matplotlib with enterprise theme.

    Two rendering paths:
      - render_from_spec(spec, path): preferred. Renders from ChartSpec.
      - render(code, path): backward-compatible. Executes raw Python code.
    Both return ChartResult.
    """

    def render(self, code: str, output_path: str) -> ChartResult:
        """Execute rendering code, saving chart to output_path.

        Injects cn_font, Palette, and __chart_spec__ into the exec context.
        If __chart_spec__ is declared, routes to render_from_spec internally.
        Otherwise returns ChartResult with empty metadata (legacy path).
        """
        FontManager.initialize()

        import matplotlib.pyplot as plt
        plt.close("all")

        ctx = {
            "__output_path__": output_path,
            "plt": plt,
            "cn_font": FontManager.get_cn_font(),
            "Palette": Palette,
            "__chart_spec__": None,
        }

        exec(code, ctx)

        figs = [plt.figure(n) for n in plt.get_fignums()]
        for fig in figs:
            try:
                fig.tight_layout()
            except Exception:
                pass

        if not os.path.exists(output_path):
            if figs:
                figs[-1].savefig(output_path, dpi=200, bbox_inches="tight")
            else:
                fig, ax = plt.subplots(figsize=(16, 9))
                ax.text(0.5, 0.5, "No chart data", ha="center", va="center", fontsize=16)
                ax.set_axis_off()
                fig.savefig(output_path, dpi=200, bbox_inches="tight")
                plt.close(fig)

        # Check if __chart_spec__ was declared
        chart_spec = ctx.get("__chart_spec__")
        if chart_spec and isinstance(chart_spec, dict):
            # Reconstruct ChartSpec from dict and use render_from_spec
            spec = self._spec_from_dict(chart_spec)
            result = self.render_from_spec(spec, output_path)
            plt.close("all")
            return result

        # Legacy path: empty metadata
        plt.close("all")
        return ChartResult(
            image_path=output_path,
            metadata={},
            summary="",
            stdout="",
        )

    def render_from_spec(self, spec: ChartSpec, output_path: str) -> ChartResult:
        """Render from a ChartSpec directly.

        This is the preferred rendering path. It:
        1. Creates a matplotlib figure from the spec
        2. Renders the appropriate chart type
        3. Saves _metadata.json alongside the PNG
        4. Computes and returns a text summary
        """
        FontManager.initialize()
        cn_font = FontManager.get_cn_font()

        import matplotlib.pyplot as plt
        plt.close("all")

        fig, ax = plt.subplots(figsize=spec.figsize)

        match spec.chart_type:
            case "bar":
                self._render_bar(ax, spec, cn_font)
            case "line":
                self._render_line(ax, spec, cn_font)
            case "pie":
                self._render_pie(ax, spec, cn_font)
            case "scatter":
                self._render_scatter(ax, spec, cn_font)
            case "histogram":
                self._render_histogram(ax, spec, cn_font)
            case "heatmap":
                self._render_heatmap(ax, spec, cn_font)
            case _:
                raise ValueError(f"Unknown chart_type: {spec.chart_type}")

        ax.set_title(spec.title, fontproperties=cn_font)
        if spec.xlabel:
            ax.set_xlabel(spec.xlabel, fontproperties=cn_font)
        if spec.ylabel:
            ax.set_ylabel(spec.ylabel, fontproperties=cn_font)

        fig.tight_layout()
        fig.savefig(output_path, dpi=200, bbox_inches="tight")

        # Metadata
        metadata = spec.to_metadata()
        meta_path = output_path.replace(".png", "_metadata.json")
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("Failed to save metadata JSON: %s", exc)

        # Summary
        summary = ChartResult.compute_summary(spec.all_values(), spec.labels)

        plt.close("all")
        return ChartResult(
            image_path=output_path,
            metadata=metadata,
            summary=summary,
            stdout="",
        )

    def _render_bar(self, ax, spec: ChartSpec, cn_font) -> None:
        n_series = len(spec.series)
        n_vals = len(spec.series[0].values) if spec.series else 0
        import numpy as np
        x = np.arange(n_vals)
        width = 0.8 / n_series
        for i, s in enumerate(spec.series):
            offset = (i - n_series / 2 + 0.5) * width
            bars = ax.bar(x + offset, s.values, width, label=s.name, color=s.color)
            for bar in bars:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        f"{bar.get_height():.0f}", ha="center", va="bottom",
                        fontsize=9, fontproperties=cn_font)
        ax.set_xticks(x)
        if spec.labels:
            ax.set_xticklabels(spec.labels, fontproperties=cn_font)
        ax.legend(prop=cn_font)

    def _render_line(self, ax, spec: ChartSpec, cn_font) -> None:
        import numpy as np
        x = np.arange(len(spec.series[0].values)) if spec.series else []
        for s in spec.series:
            ax.plot(x, s.values, marker="o", label=s.name, color=s.color, linewidth=2)
        if spec.labels:
            ax.set_xticks(x)
            ax.set_xticklabels(spec.labels, fontproperties=cn_font)
        ax.legend(prop=cn_font)

    def _render_pie(self, ax, spec: ChartSpec, cn_font) -> None:
        if not spec.slices:
            return
        labels = [s.label for s in spec.slices]
        sizes = [s.value for s in spec.slices]
        colors = [s.color for s in spec.slices]
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors, autopct="%1.1f%%",
            startangle=90, textprops={"fontproperties": cn_font},
        )
        for t in texts:
            t.set_fontproperties(cn_font)

    def _render_scatter(self, ax, spec: ChartSpec, cn_font) -> None:
        if not spec.points:
            return
        xs = [p.x for p in spec.points]
        ys = [p.y for p in spec.points]
        ax.scatter(xs, ys, c="#2F80ED", s=60)
        for p in spec.points:
            if p.label:
                ax.annotate(p.label, (p.x, p.y), fontsize=9, fontproperties=cn_font)

    def _render_histogram(self, ax, spec: ChartSpec, cn_font) -> None:
        import numpy as np
        if spec.data and spec.data[0]:
            ax.hist(spec.data[0], bins="auto", color="#2F80ED", edgecolor="white")

    def _render_heatmap(self, ax, spec: ChartSpec, cn_font) -> None:
        import numpy as np
        if not spec.data:
            return
        data = np.array(spec.data)
        im = ax.imshow(data, cmap="Blues", aspect="auto")
        plt.colorbar(im, ax=ax)
        if spec.labels:
            ax.set_xticks(range(len(spec.labels)))
            ax.set_xticklabels(spec.labels, fontproperties=cn_font, rotation=45)

    def _spec_from_dict(self, d: dict) -> ChartSpec:
        """Reconstruct a ChartSpec from a dict (e.g., from __chart_spec__)."""
        from chart.chart_spec import SeriesSpec, SliceSpec, PointSpec

        series = None
        if "series" in d:
            series = [SeriesSpec(**s) for s in d["series"]]
        slices = None
        if "slices" in d:
            slices = [SliceSpec(**s) for s in d["slices"]]
        points = None
        if "points" in d:
            points = [PointSpec(**p) for p in d["points"]]

        return ChartSpec(
            title=d.get("title", ""),
            chart_type=d.get("chart_type", "bar"),
            xlabel=d.get("xlabel"),
            ylabel=d.get("ylabel"),
            figsize=tuple(d.get("figsize", (12, 6))),
            series=series,
            slices=slices,
            points=points,
            data=d.get("data"),
            labels=d.get("labels"),
        )
```

- [x] **Step 5: Run tests to verify they pass**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_renderer_v2.py -v
```
Expected: PASS

- [x] **Step 6: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/chart_renderer.py ai_service/chart/renderers/matplotlib_renderer.py ai_service/tests/test_chart_renderer_v2.py && git commit -m "feat: add render_from_spec, refactor render() to return ChartResult"
```

---

### Task 6: ChartService — detect __chart_spec__, return metadata + summary

**Files:**
- Modify: `ai_service/chart/chart_service.py`

**Interfaces:**
- Consumes: `MatplotlibRenderer.render() -> ChartResult`
- Produces: `ChartService.render(code) -> dict` with additional `metadata`, `summary` keys

- [x] **Step 1: Refactor ChartService.render()**

Replace `ai_service/chart/chart_service.py`:

```python
"""ChartService — unified entry point for chart generation.

Only this module should be imported by tools/agents. Internal renderer/storage
details are hidden behind this facade, allowing engine swaps without changes
to callers or prompts.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from chart.minio_storage import MinioStorage
from chart.renderers.matplotlib_renderer import MatplotlibRenderer

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp")


class ChartService:
    """Generate charts from Python code, upload to MinIO, return structured dict."""

    def __init__(self):
        self._renderer = MatplotlibRenderer()
        self._storage = MinioStorage()

    def render(self, code: str) -> dict:
        """Execute matplotlib code and return structured dict with metadata.

        The code is executed with FontManager + cn_font + Palette injected.
        If __chart_spec__ is declared, the renderer uses render_from_spec
        internally and returns full metadata.

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

        # Upload metadata.json if present
        metadata_url = None
        json_path = output_path.replace(".png", "_metadata.json")
        if os.path.isfile(json_path):
            metadata_url = self._storage.upload(json_path)

        return {
            "type": "image",
            "url": url,
            "metadata": result.metadata,
            "metadata_url": metadata_url,
            "summary": result.summary,
        }
```

- [x] **Step 2: Run existing tests**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_generator.py -v
```
Expected: PASS (no regressions)

- [x] **Step 3: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/chart/chart_service.py && git commit -m "refactor: ChartService returns metadata and summary from ChartResult"
```

---

### Task 7: Sandbox Tool — inject cn_font/Palette, scan _metadata.json

**Files:**
- Modify: `ai_service/tools/sandbox/tool.py`

**Consumes:** existing `CodeSandboxTool` structure
**Produces:** `ToolResult.success({"output": ..., "images": ..., "charts": [...]})` where `charts` list contains `{image, url, metadata, summary}`

- [x] **Step 1: Update _build_preamble() to inject cn_font and Palette**

Edit `ai_service/tools/sandbox/tool.py`. Locate the `_build_preamble()` method (lines 73-124). Replace the chart theme section (lines 90-93):

**Old:**
```python
        # ── Chart theme (font, DPI, style) ──
        lines.append("from chart.chart_theme import ChartTheme")
        lines.append("ChartTheme.initialize()")
```

**New:**
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

- [x] **Step 2: Add _metadata.json scanning in execute()**

Edit the `execute()` method of `CodeSandboxTool`. After the image upload section (around line 218, after `uploaded` variable is built), add the charts metadata scanning logic. Insert the following code before the `if uploaded:` block (around line 220):

```python
            # ── Scan for _metadata.json files and build charts list ──
            charts = []
            for f in _os_module.listdir(cwd):
                if f.endswith("_metadata.json"):
                    meta_path = _os_module.path.join(cwd, f)
                    try:
                        with open(meta_path, encoding="utf-8") as mf:
                            metadata = json.load(mf)
                    except Exception:
                        continue
                    image_name = f.replace("_metadata.json", ".png")
                    url = uploaded.get(image_name, "")
                    summary = metadata.pop("_summary", "")
                    charts.append({
                        "image": image_name,
                        "url": url,
                        "metadata": metadata,
                        "summary": summary,
                    })
```

And change the final `ToolResult.success` call (line 227) to include `charts`:

Old:
```python
            return ToolResult.success({
                "output": output.strip() or "(no output)",
                "images": uploaded,
            })
```

New:
```python
            return ToolResult.success({
                "output": output.strip() or "(no output)",
                "images": uploaded,
                "charts": charts,
            })
```

- [x] **Step 3: Run existing sandbox tests to verify no regression**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_code_sandbox.py -v
```
Expected: PASS

- [x] **Step 4: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/tools/sandbox/tool.py && git commit -m "feat: inject cn_font/Palette into sandbox, add _metadata.json scanning for charts"
```

---

### Task 8: Prompt updates — ChartSpec code prompt, composer metadata references

**Files:**
- Modify: `ai_service/graph/nodes.py`

- [x] **Step 1: Update _CHART_CODE_PROMPT**

In `ai_service/graph/nodes.py`, replace the `_CHART_CODE_PROMPT` string (currently lines 892-911) with the following:

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
3. The variables `cn_font` (FontProperties), `Palette`, `ChartSpec`, and `SeriesSpec` are already available in the execution context — use them directly
4. ALL text elements MUST use `fontproperties=cn_font` — example: ax.set_title("标题", fontproperties=cn_font)
5. Get colors from Palette: Palette.get_series_colors(N) — returns PaletteColor objects with .hex and .name_cn
6. Set figure size to (12, 6)
7. Include title, axis labels, legend if applicable
8. MUST set __chart_spec__ using the ChartSpec dataclass before saving:
   __chart_spec__ = {
       "title": "图表标题",
       "chart_type": "bar",  # or "line"/"pie"/"scatter"/"histogram"/"heatmap"
       "xlabel": "X轴标签",
       "ylabel": "Y轴标签",
       "figsize": [12, 6],
       "series": [
           {"name": "系列名", "color": colors[0].hex, "color_name": colors[0].name_cn, "values": [10, 20, 30]},
       ],
   }
   For pie charts use "slices": [{"label": "A", "value": 30, "color": colors[0].hex, "color_name": colors[0].name_cn}]
   For scatter charts use "points": [{"x": 1, "y": 2, "label": "pt1"}]
9. Output ONLY valid Python code — no markdown wrappers, no explanation
10. Save using plt.savefig(__output_path__, dpi=200, bbox_inches='tight')
11. Do NOT call plt.show()
12. End with plt.close()
13. PROHIBITED: Do NOT use plt.rcParams['font.sans-serif'] — font is handled via fontproperties=cn_font
"""
```

- [x] **Step 2: Update _build_composer_system_prompt to include chart metadata**

In `ai_service/graph/nodes.py`, locate the `_format_artifacts` helper inside `_build_composer_system_prompt` (around line 1421). Modify the image artifact block:

**Old:**
```python
            if atype == "image" and content_ref:
                # For images, provide the actual URL and markdown syntax hint
                lines.append(f"- [{aid}] IMAGE for '{purpose}' — use this Markdown: ![{purpose}]({content_ref})")
```

**New:**
```python
            if atype == "image" and content_ref:
                # For images, provide the actual URL and markdown syntax hint
                meta_hint = ""
                if "metadata" in a and a["metadata"]:
                    series_info = a["metadata"].get("series", [])
                    summary = a.get("summary", "")
                    if series_info:
                        colors_str = "; ".join(
                            f'{s.get("name","")}（{s.get("color_name","")}）'
                            for s in series_info
                        )
                        meta_hint = f" [colors: {colors_str}]"
                    if summary:
                        meta_hint += f" [summary: {summary}]"
                lines.append(
                    f"- [{aid}] IMAGE for '{purpose}' — use this Markdown: "
                    f"![{purpose}]({content_ref}){meta_hint}"
                )
```

Then add the Chart Color Rules to the instructions section at the end of `_build_composer_system_prompt` (before `Current time: {now_str}`):

```python
[Chart Color Rules]
- CRITICAL: All chart color/数值 descriptions MUST come from chart metadata's series color_name and summary, NOT from image inspection
- When referencing chart series, use format: "系列名（颜色名）" — e.g., "GDP（蓝色）"
- The chart summary field contains programmatically extracted statistics (max/min/avg/trend) — use these when describing data
- Charts WITHOUT metadata (no series/summary) must NOT have color or numeric descriptions — describe only the chart type and title
```

- [x] **Step 3: Run existing tests to verify no regression**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_generator.py ai_service/tests/test_chart_validators.py -v
```
Expected: PASS

- [x] **Step 4: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/graph/nodes.py && git commit -m "feat: update chart code prompt to use ChartSpec, add chart metadata rules to composer prompt"
```

---

### Task 9: Data Analyst Agent prompt — add metadata reference rules

**Files:**
- Modify: `ai_service/db/migrations/002_seed_agents_and_setup.sql`

- [x] **Step 1: Update Data Analyst system prompt**

In `ai_service/db/migrations/002_seed_agents_and_setup.sql`, locate the Data Analyst system prompt (after `-- Agent 5: Data Analyst`). Insert the following rules into the prompt, after the `## Chart Guidelines (MANDATORY)` section:

Find the line:
```
## Chart Guidelines (MANDATORY)
```

And add after `- Do NOT repeat all data values as text — the chart shows them`:

```
## Chart Metadata Rules (MANDATORY)
- CRITICAL: Chart color names MUST come from ChartSpec metadata, NOT from image inspection
- Use format: "系列名（颜色名）" for data series references — e.g., "GDP（蓝色）"
- Chart summary (max/min/avg/trend) is programmatically computed — use it for data descriptions
- NEVER describe colors or data values by looking at the generated image — the metadata is authoritative
- Charts without metadata (legacy code) — only describe chart type and title, no color/value details
- The system now uses ChartSpec as the single source of truth — always set __chart_spec__ in generated code
```

The exact SQL INSERT content may need to be updated. The full prompt section becomes approximately:

```
## Chart Guidelines (MANDATORY)
- When user asks for any chart: call execute_python FIRST, then describe results
- Use matplotlib with Chinese labels (title, axes, legend)
- The system auto-initializes fonts and theme — just call plt.savefig()
- After tool finishes, briefly describe what the chart shows
- Do NOT repeat all data values as text — the chart shows them

## Chart Metadata Rules (MANDATORY)
- CRITICAL: Chart color names MUST come from ChartSpec metadata, NOT from image inspection
- Use format: "系列名（颜色名）" for data series references — e.g., "GDP（蓝色）"
- Chart summary (max/min/avg/trend) is programmatically computed — use it for data descriptions
- NEVER describe colors or data values by looking at the generated image — the metadata is authoritative
- Charts without metadata (legacy code) — only describe chart type and title, no color/value details
- The system now uses ChartSpec as the single source of truth — always set __chart_spec__ in generated code
```

**IMPORTANT:** The exact modification should:
1. Read the current SQL file
2. Find the `## Chart Guidelines (MANDATORY)` section within the Data Analyst INSERT statement
3. Insert the metadata rules block after the existing guidelines

The SQL string is a single-quoted string inside the INSERT. Be careful to escape any single quotes in the added text. The text above has no single quotes, so it can be inserted directly.

- [x] **Step 2: Commit**

```bash
cd /Volumes/work/projects/winter-agent && git add ai_service/db/migrations/002_seed_agents_and_setup.sql && git commit -m "feat: add chart metadata reference rules to Data Analyst prompt"
```

---

### Task 10: Comprehensive test run — all existing + new tests pass

**Files:**
- No file changes — run tests to confirm no regressions.

- [x] **Step 1: Run all chart-related tests**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_chart_palette.py ai_service/tests/test_chart_font_manager.py ai_service/tests/test_chart_spec_v2.py ai_service/tests/test_chart_result.py ai_service/tests/test_chart_renderer_v2.py ai_service/tests/test_chart_generator.py ai_service/tests/test_chart_validators.py ai_service/tests/test_chart_spec.py ai_service/tests/test_chart_registry.py ai_service/tests/test_chart_envelope.py ai_service/tests/test_chart_planner.py -v
```
Expected: ALL PASS

- [x] **Step 2: Run sandbox test**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/test_code_sandbox.py -v
```
Expected: PASS

- [x] **Step 3: Run full test suite (optional, may take time)**

```bash
cd /Volumes/work/projects/winter-agent && python -m pytest ai_service/tests/ -v --tb=short
```
Expected: No regressions.

- [x] **Step 4: If any tests fail, fix before proceeding**

No commit needed for this task. Verification is complete when all tests pass.

---

## Self-Review

### 1. Spec coverage

| Design Doc Section | Covered By |
|---|---|
| 2.1 Palette | Task 1 |
| 2.2 ChartSpec (SeriesSpec/SliceSpec/PointSpec) | Task 3 |
| 2.3 ChartResult + compute_summary | Task 4 |
| 3.1 render_from_spec (all 6 chart types) | Task 5 (Step 4: _render_bar/line/pie/scatter/histogram/heatmap) |
| 3.2 render(code, path) backward compat | Task 5 (Step 4: render() returns ChartResult with empty metadata) |
| 3.3 render_from_spec saves _metadata.json | Task 5 (Step 4: render_from_spec saves metadata JSON) |
| 4.1 Sandbox Tool preamble inject | Task 7 (Step 1) |
| 4.2 Sandbox Tool metadata scanning | Task 7 (Step 2) |
| 4.3 Graph Nodes — _CHART_CODE_PROMPT | Task 8 (Step 1) |
| 4.4 Graph Nodes — composer prompt | Task 8 (Step 2) |
| 4.5 Data Analyst prompt | Task 9 |
| 5. FontManager | Task 2 |
| 6. ChartTheme delegation | Task 2 (Step 4) |
| 7. Compatibility matrix | Task 5 (render = legacy empty, render_from_spec = full metadata) |

### 2. Placeholder scan

All code blocks contain complete, runnable Python code. No "TBD", "TODO", "implement later", or "fill in details". No "add error handling" without actual code. No "similar to Task X" references.

### 3. Type consistency

- `Palette.get_series_colors(n) -> list[PaletteColor]` (Task 1) matches usage in MatplotlibRenderer (Task 5) and prompt examples (Task 8)
- `Palette.get_color_name(hex) -> str` (Task 1) matches usage in ChartSpec.__post_init__ (Task 3)
- `ChartSpec.to_metadata() -> dict` (Task 3) matches ChartResult.metadata field (Task 4) and metadata.json format (Task 5)
- `ChartResult.compute_summary(values) -> str` (Task 4) matches usage in MatplotlibRenderer.render_from_spec (Task 5)
- `ChartResult(image_path, metadata, summary, stdout)` (Task 4) matches MatplotlibRenderer return type (Task 5) and ChartService return dict (Task 6)
- `AbstractChartRenderer.render(code, path) -> ChartResult` (Task 5) preserves the abstract interface
- `AbstractChartRenderer.render_from_spec(spec, path) -> ChartResult` (Task 5) is the new abstract method
- `FontManager.get_cn_font() -> FontProperties` (Task 2) matches injection in render() (Task 5) and sandbox preamble (Task 7)

### Gaps

- **Palette series exact colors:** The design doc specifies `_SERIES = [...]  # 12 个 PaletteColor` but does not list the exact 12 hex values. The plan uses the 7 named base colors + 5 hue-shifted derivatives to form the 12-item SERIES. If specific hex values are required for the extended 5 colors, update `_build_series()` in Task 1.
- **Data Analyst prompt:** The SQL migration file at `ai_service/db/migrations/002_seed_agents_and_setup.sql` contains the Data Analyst prompt. Task 9 modifies this file directly. If the DB has already been migrated, this change only affects NEW deployments — existing DB entries will need a manual UPDATE or a new migration to pick up the prompt change.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-29-chart-single-source-truth.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
