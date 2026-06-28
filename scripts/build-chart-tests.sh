#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."
PYTHONPATH="$PWD/ai_service:$PYTHONPATH" /Volumes/work/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest ai_service/tests/test_chart_font_manager.py ai_service/tests/test_chart_palette.py ai_service/tests/test_chart_renderer_v2.py -q
