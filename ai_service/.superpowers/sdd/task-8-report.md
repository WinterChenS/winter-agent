# Task 8: Prompt updates — _CHART_CODE_PROMPT and Composer prompt

## Status
DONE

## Commit
`3b3d62c` feat: update chart code prompt to use cn_font/Palette, add chart metadata to composer prompt

## Test results
- **Syntax check**: PASS (`python3 -m py_compile graph/nodes.py`)
- **Verify imports**: All assertions PASSED (cn_font, Palette, __chart_metadata__, FontManager, Chart Color Rules)
- **Existing tests (`test_chart_generator.py`, `test_chart_validators.py`)**: Both fail due to pre-existing issues (Python 3.9 `dataclass(slots=True)` incompatibility and missing `graph.chart_generator` module). Identical failures confirmed on clean git state.

## Changes made

### 1. `_CHART_CODE_PROMPT` (line 892)
- **Rule 3**: Replaced `plt.rcParams['font.sans-serif']` font setup with `cn_font` (FontManager) — LLM now uses `fontproperties=cn_font` for all Chinese text
- **Rule 4**: Replaced generic color advice with `Palette` API — `Palette.get_series_colors(n)`, `Palette.PRIMARY.hex`, etc.
- **New Rule 11**: Added optional `__chart_metadata__` dict instruction for title, chart_type, xlabel, ylabel, series, source

### 2. Fallback chart code (line 963)
- Imports `FontManager` and `Palette` from the `chart` module
- Uses `cn_font` via `FontManager.get_cn_font()`
- Uses `Palette.PRIMARY.hex` for the line color
- Switched from `plt.plot`/`plt.title` to `ax.set_title(..., fontproperties=cn_font)` pattern for fontproperties support

### 3. `_build_composer_system_prompt` (line 1409)
- **`_format_artifacts`**: Image artifacts now show URL and Markdown syntax on separate lines; added metadata comment about `{file}_metadata.json` structure
- **Instructions**: Added chart metadata hint telling composer to incorporate chart metadata (title, series, source) into surrounding text
- **New `[Chart Color Rules]` section**: Lists all 12 Palette Chinese color names (蓝色, 绿色, 深绿, 橙色, 红色, 紫色, 粉红, 青色, 琥珀, 青绿, 靛蓝, 棕色), explains series-to-color assignment order, encourages using Chinese color names for precision

## Concerns
None. The test failures are pre-existing and unrelated to these changes.
