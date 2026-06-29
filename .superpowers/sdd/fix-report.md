# Fix Report: chart-single-source-truth review findings

**Branch:** feature/20260629/chart-single-source-truth
**Date:** 2026-06-29
**Status:** All 3 IMPORTANT fixes applied, 38/38 tests passing (including 3 new TDD tests)

---

## I-1: `all_values()` missing `data` field for histogram/heatmap

**File:** `ai_service/chart/chart_spec.py`
**Fix:** Added `self.data` iteration to `all_values()` — each row is flattened into the values list.
**TDD:** Wrote `test_histogram_data_values` and `test_heatmap_data_values`, both failed (returned `[]`), then fixed.

## I-2: Scatter hardcoded color

**File:** `ai_service/chart/renderers/matplotlib_renderer.py`
**Fix:** Changed `c="#2F80ED"` to `c=Palette.PRIMARY.hex` in `_render_scatter()`.
**Note:** Scatter metadata is limited to xlabel/ylabel/title per `to_metadata()` — this is documented (not all chart types expose full point data in metadata).

## I-3: SSL warning (note only)

**File:** `ai_service/tools/sandbox/tool.py`
**Fix:** Added security comment above the SSL disable line, documenting the MITM risk and recommending future remediation. Not fixing the behavior now as specified.

## I-4: metadata JSON missing `_summary` key

**File:** `ai_service/chart/renderers/matplotlib_renderer.py`
**Fix:** Moved `compute_summary()` call before metadata serialization, added `metadata["_summary"] = summary` so the sandbox tool's `metadata.pop("_summary", "")` finds the value.
**TDD:** Wrote `test_metadata_json_includes_summary_key`, which failed (`_summary` not in JSON), then fixed.

---

## Test Results

```
38 passed in 0.81s
```

Covering test files:
- `ai_service/tests/test_chart_spec_v2.py` — 3 new tests + existing
- `ai_service/tests/test_chart_renderer_v2.py` — 1 new test + existing
- `ai_service/tests/test_chart_result.py` — existing (no changes needed)
