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

---

### 6. CRITICAL C2: Chart metadata never reaches the composer prompt

**Problem:** `_register_artifact()` in `execution_node` stored only `artifact_id`, `type`, `purpose`, `source_step_id`, `content_ref` for chart artifacts. The `metadata` and `summary` fields available from the chart step context (chart type, step description) were never attached to the artifact entry. Meanwhile, `_format_artifacts` in `_build_composer_system_prompt()` could not access these fields because they were never stored.

**Fix (3 changes in `ai_service/graph/nodes.py`):**

1. **`_register_artifact` (line 1034):** Added optional `metadata: dict | None = None` and `summary: str | None = None` parameters. When provided, these are stored in the artifact entry dict, making them available to the composer prompt.

2. **`execution_node` call site (line 1316):** At the chart artifact registration point, the fix:
   - Extracts `chart_type` from `expected_artifacts[0].get("chart_type")`
   - Passes `metadata={"chart_type": chart_type, "filename": fname}` — the chart type (line/bar/pie/etc.) and image filename
   - Passes `summary=step.get("description", "")[:200]` — the step description as chart summary

3. **`_format_artifacts` (line 1438):** Updated to read `a.get("metadata")` and `a.get("summary")` from each artifact. When present, the summary is rendered as an indented `Summary:` line and the metadata key-value pairs are rendered as a `Metadata:` line appended to the image artifact entry.

**Result:** The composer system prompt now includes chart type and description context for each chart image artifact, enabling the LLM to better describe and reference the visual assets in the final report.

**Files changed:** `ai_service/graph/nodes.py` — modified `_register_artifact`, execution_node chart artifact registration, and `_format_artifacts`.
