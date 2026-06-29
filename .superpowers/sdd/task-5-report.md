# Task 5 Report: ChartRenderer — render_from_spec, ChartResult return type

## Summary

Successfully completed Task 5. All 10 new tests pass, all 45 existing chart tests pass.

## Changes

### Modified: `ai_service/chart/chart_renderer.py`
- Changed `render()` return type from `str` to `ChartResult`
- Added abstract method `render_from_spec(spec: ChartSpec, output_path: str) -> ChartResult`
- New imports: `ChartResult`, `ChartSpec`

### Modified: `ai_service/chart/renderers/matplotlib_renderer.py`
- `render(code, path)` -> `ChartResult`: Now returns `ChartResult` with empty metadata `{}` and empty summary `""` for legacy code (backward compat)
- `render_from_spec(spec, path)` -> `ChartResult`: New method renders all 6 chart types (bar/line/pie/scatter/histogram/heatmap)
  - Uses Palette colors from spec (spec.series[i].color for hex)
  - All text uses `fontproperties=cn_font` (from FontManager)
  - Saves `{basename}_metadata.json` alongside PNG with `json.dump(ensure_ascii=False)`
  - Calls `ChartResult.compute_summary()` for auto summary
- `render()` injects `cn_font`, `Palette`, `__chart_spec__` into exec context
- If `__chart_spec__` dict is found in exec context, routes to `render_from_spec` internally
- Added `_spec_from_dict()` helper to reconstruct ChartSpec from dict
- Added `_render_bar`, `_render_line`, `_render_pie`, `_render_scatter`, `_render_histogram`, `_render_heatmap` private methods

### Created: `ai_service/tests/test_chart_renderer_v2.py`
- `TestRenderFromSpec`: 6 tests covering all 4 tested chart types (bar, line, pie, scatter), metadata JSON creation, and summary content
- `TestRenderBackwardCompat`: 4 tests covering backward-compatible render returns ChartResult, empty metadata, empty summary, and cn_font injection

## Verification

- Red phase: All 10 tests failed as expected (AttributeError for missing method, AssertionError for wrong return type, NameError for missing cn_font)
- Green phase: All 10 tests pass
- Regression: All 45 existing chart tests still pass (test_chart_spec, test_chart_palette, test_chart_font_manager)
