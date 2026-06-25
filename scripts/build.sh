#!/bin/bash
cd "$(dirname "$0")/../ai_service" && .venv/bin/python -m pytest tests/ --ignore=tests/test_chart_generator.py --ignore=tests/test_chart_planner.py --ignore=tests/test_chart_envelope.py --ignore=tests/test_chart_registry.py --ignore=tests/test_chart_event_mapper.py -q
