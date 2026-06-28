# Task 4: ChartTheme refactor — delegate font to FontManager

## Status
DONE

## Commits
- `ecaa818` refactor: ChartTheme delegates font to FontManager, removes _find_chinese_font

## Verification done
1. `ChartTheme.initialize()` runs successfully — prints "OK"
2. `_find_chinese_font` import raises ImportError as expected — confirmed removed

## Concerns
None. The refactor cleanly delegates all font discovery and caching to FontManager, drops the standalone `_find_chinese_font()` function, and removes the `matplotlib.font_manager` import along with `font.sans-serif` rcParams configuration. All remaining non-font rcParams (DPI, figure size, grid, font sizes, line width, savefig settings) are preserved unchanged.
