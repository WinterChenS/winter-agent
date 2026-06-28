# Task 8 Fix Report

## Summary

Fixed 4 MAJOR spec deviations in `ai_service/graph/nodes.py` found during review of Task 8 implementation.

## Fixes Applied

### 1. `__chart_metadata__` structure (line 909)
**Before:** Optional flat dict with keys: `title`, `chart_type`, `xlabel`, `ylabel`, `series` (list of str), `source`
**After:** Mandatory rule with specific nested dict structure before saving:
- `chart_type`: string (e.g., "bar")
- `title`: string
- `series`: list of objects with `name`, `color` (colors[n].hex), `color_name` (colors[n].name_cn)
- `summary`: string — one-sentence chart description

### 2. `plt.savefig` filename (line 919 + line 991)
**Before:** `plt.savefig('chart_output.png', dpi=200, bbox_inches='tight')` in main prompt AND fallback code
**After:** `plt.savefig(__output_path__, dpi=200, bbox_inches='tight')` in both locations

### 3. PROHIBITED rule 13 (line 922)
Added exactly: `PROHIBITED: Do NOT use plt.rcParams['font.sans-serif'] — font is handled via fontproperties=cn_font`

### 4. `_format_artifacts` runtime metadata extraction (lines 1443-1457)
**Before:** Static comment `# Metadata hint: each chart may have a corresponding {file}_metadata.json...`
**After:** Runtime reading of `a["metadata"]["series"]` and `a.get("summary", "")` to generate inline color/summary hints appended to the image artifact line.

## Files Changed
- `ai_service/graph/nodes.py`: 33 insertions, 14 deletions

## Tests
- `test_chart_validators.py`: 9/9 PASSED
- `test_multi_agent_graph.py`: 2/2 PASSED
- `test_chart_generator.py`: SKIPPED (pre-existing: module `graph.chart_generator` does not exist)

---

### 5. CRITICAL: `__output_path__` missing in sandbox preamble (tool.py)

**Problem:** `_CHART_CODE_PROMPT` (nodes.py, line 919) instructs the LLM to use `plt.savefig(__output_path__, ...)`, and both the main prompt and fallback code reference `__output_path__`. The `MatplotlibRenderer` injects it into `exec()` context, so direct renderer usage works. However, the **Plan-Execute-Compose flow** uses the sandbox subprocess (`CodeSandboxTool`), whose `_build_preamble()` defined `cn_font` and `Palette` but never defined `__output_path__`. This caused a `NameError` at runtime when the sandbox executed the LLM-generated chart code.

**Fix:** Added `__output_path__ = 'chart_output.png'` to the sandbox preamble in `_build_preamble()`, right after the `Palette` injection (line 98-99 of `ai_service/tools/sandbox/tool.py`). This ensures the variable exists in the subprocess global scope.

**Rationale for filename choice (`chart_output.png`):**
- Consistent with the original filename used before the `__output_path__` change
- The sandbox's `_auto_save_figures()` atexit hook tracks explicitly-saved figures (via a patched `savefig`), so it won't duplicate the save
- The post-execution MinIO upload scanner (tool.py lines 211-223) scans CWD for any PNG files, so `chart_output.png` will be found and uploaded

**File changed:** `ai_service/tools/sandbox/tool.py` — 3 lines added
