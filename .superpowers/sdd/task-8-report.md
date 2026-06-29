# Task 8 Report: Prompt updates — ChartSpec code prompt, composer metadata references

## Summary

Updated two prompts in `ai_service/graph/nodes.py` to use the new ChartSpec API and enable metadata-driven analysis in the composer:

### Step 1: `_CHART_CODE_PROMPT`
Replaced the prompt with a new version that:
- Instructs LLM to build ChartSpec with chart_type, title, series/slices/points, labels
- Uses `Palette.get_series_colors(N)` for enterprise colors (PaletteColor with .hex and .name_cn)
- Uses `fontproperties=cn_font` for ALL matplotlib text APIs
- Prohibits `plt.rcParams['font.sans-serif']` — font handled via fontproperties
- Sets `__chart_spec__` as a dict so MatplotlibRenderer can detect and re-render via `render_from_spec`
- Outputs ONLY valid Python code — no markdown, no explanation

### Step 2: `_build_composer_system_prompt`
Enhanced `_format_artifacts` to include chart metadata:
- For artifacts with `metadata.series`: includes color names (e.g., "GDP（蓝色）; CPI（绿色）")
- For artifacts with `summary`: includes summary text
- Artifacts without metadata are rendered without color/numeric hints

Added Chart Color Rules section to the composer instructions:
- Colors/values MUST come from chart metadata, NOT image inspection
- Series format: "系列名（颜色名）"
- Summary field used for data statistics
- Charts WITHOUT metadata: no color/numeric descriptions

## TDD Process

1. **RED**: Wrote 19 tests across 3 test classes — 16 failed correctly (features not yet implemented)
2. **GREEN**: Updated `_CHART_CODE_PROMPT` and `_build_composer_system_prompt` — 19/19 tests pass
3. **Regression**: All 121 existing tests pass (test_chart_validators, test_chart_spec_v2, etc.)

## Key Files Modified
- `ai_service/graph/nodes.py` — `_CHART_CODE_PROMPT` (replaced entire prompt), `_build_composer_system_prompt` (formatted artifacts + Chart Color Rules)

## Test Files
- `ai_service/tests/test_nodes_prompts.py` — 19 new tests covering prompt content, artifact formatting, and Chart Color Rules
