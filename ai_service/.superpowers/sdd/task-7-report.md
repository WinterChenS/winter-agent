# Task 7: Sandbox preamble — inject cn_font and Palette

## Summary

Added `cn_font` (via `FontManager.get_cn_font()`) and `Palette` injection into the `CodeSandboxTool._build_preamble()` method in `ai_service/tools/sandbox/tool.py`. These imports make Chinese font support and a Chinese-themed color palette available in every sandbox code execution session, enabling chart generation with proper CJK text rendering and culturally appropriate colors.

## Changes

**File:** `ai_service/tools/sandbox/tool.py`

In the `_build_preamble()` static method, added the following lines after the existing `ChartTheme.initialize()` call:

```python
# ── Inject cn_font and Palette for chart generation ──
lines.append("from chart.font_manager import FontManager")
lines.append("cn_font = FontManager.get_cn_font()")
lines.append("from chart.palette import Palette")
```

## Verification

- **Python syntax:** `python3 -m py_compile tools/sandbox/tool.py` — PASS (Syntax OK)
- **Module import:** blocked by pre-existing Python 3.9 `dataclass(slots=True)` incompatibility (pre-existing, unrelated)
- **Sandbox tests:** blocked by same pre-existing Python 3.9 incompatibility (pre-existing, unrelated)
- **Git:** committed with message `feat: inject cn_font and Palette into sandbox preamble`

## Commit

`13403e9` feat: inject cn_font and Palette into sandbox preamble
