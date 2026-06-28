# Task 5: MatplotlibRenderer refactor — return ChartResult, inject cn_font, extract metadata, validate fonts

## Status
DONE

## Commits
- `23bbee8` refactor: MatplotlibRenderer returns ChartResult, injects cn_font, extracts metadata

## Test results
- 8 passed, 0 failed, 0 errors (test_chart_renderer_v2.py)
- 25 existing chart tests still pass (zero regressions)
- Total: 33 passed

## Changes made
1. **`ai_service/chart/chart_renderer.py`**: Updated `AbstractChartRenderer.render()` return type from `str` to `ChartResult`; added `ChartResult` import.

2. **`ai_service/chart/renderers/matplotlib_renderer.py`**: Full refactor —
   - `render()` now returns `ChartResult` instead of `str`
   - Injects `cn_font` (FontManager.get_cn_font()) and `__chart_metadata__` (None default) into exec context
   - Two-level metadata extraction: L1 (declared `__chart_metadata__` dict) with L2 fallback (figure state: axis labels, legend series)
   - Post-exec font validation via `FontManager.validate_figure_fonts()`
   - Saves `{output_name}_metadata.json` alongside PNG via `_save_metadata()`
   - New helper methods: `_extract_metadata()`, `_extract_l1()`, `_extract_l2()`, `_l2_fill_gaps()`, `_save_metadata()`

3. **`ai_service/tests/test_chart_renderer_v2.py`**: Created with 8 tests covering:
   - ChartResult return type and image_path
   - L1 metadata extraction (title, chart_type, xlabel, ylabel, series)
   - Summary extraction from `__chart_metadata__`
   - metadata.json file creation
   - L2 fallback when `__chart_metadata__` is absent
   - cn_font injection into exec context

## Note
`plt.close(fig)` was removed from test code snippets because the renderer already handles `plt.close("all")` at the end, and figures need to remain open for L2 fallback inspection.
