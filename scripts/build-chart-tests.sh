#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

if [[ -n "${PYTHON_BIN:-}" ]]; then
	PYTHON="$PYTHON_BIN"
elif [[ -x "$PWD/ai_service/.venv/bin/python" ]]; then
	PYTHON="$PWD/ai_service/.venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
	PYTHON="$(command -v python3.12)"
elif command -v python3.11 >/dev/null 2>&1; then
	PYTHON="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
	PYTHON="$(command -v python3)"
else
	echo "ERROR: No suitable Python interpreter found for chart tests" >&2
	exit 1
fi

PYTHONPATH="$PWD/ai_service:$PYTHONPATH" "$PYTHON" -m pytest \
	ai_service/tests/test_chart_font_manager.py \
	ai_service/tests/test_chart_palette.py \
	ai_service/tests/test_chart_renderer_v2.py -q
