# Task 6: ChartService — upload metadata.json, return structured response

## Status
DONE

## Commits
- `d99b3a6` refactor: ChartService returns ChartResult metadata, uploads metadata.json

## Verification
- `python -c "from chart.chart_service import ChartService; print('OK')"` passed

## Changes made
1. **`ai_service/chart/chart_service.py`**: Refactored `ChartService.render()` to:
   - Capture the `ChartResult` returned by `MatplotlibRenderer.render()` (carries metadata + summary)
   - Upload `metadata.json` (saved by renderer alongside PNG) to MinIO
   - Return structured dict with `type`, `url`, `metadata`, `metadata_url`, `summary`
   - Added `json` and `os` imports for metadata.json path handling and file existence check
