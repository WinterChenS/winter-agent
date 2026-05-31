import pytest
from graph.validators import validate_chart_specs, MAX_DATA_POINTS


def test_validate_empty_list():
    assert validate_chart_specs([]) == []


def test_validate_non_dict_skipped():
    assert validate_chart_specs(["not-a-dict", 123, None]) == []


def test_validate_basic_chart():
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "bar",
        "title": "Test Chart",
        "data": [{"name": "A", "value": 10}, {"name": "B", "value": 20}],
    }])
    assert len(result) == 1
    assert result[0]["chartType"] == "bar"
    assert len(result[0]["data"]) == 2


def test_validate_chart_type_fallback():
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "invalid_type",
        "title": "Test",
        "data": [{"name": "A", "value": 1}],
    }])
    assert result[0]["chartType"] == "bar"


def test_validate_no_data_skipped():
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "bar",
        "title": "Empty",
        "data": [],
    }])
    assert result == []


def test_validate_invalid_data_points_skipped():
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "bar",
        "title": "Bad Data",
        "data": [
            {"name": "", "value": 10},
            {"name": "B", "value": "not-a-number"},
            {"name": "C", "value": 30},
        ],
    }])
    assert len(result[0]["data"]) == 1
    assert result[0]["data"][0]["name"] == "C"


def test_validate_truncates_over_max():
    data = [{"name": f"Item{i}", "value": i} for i in range(MAX_DATA_POINTS + 10)]
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "bar",
        "title": "Large",
        "data": data,
    }])
    assert len(result[0]["data"]) == MAX_DATA_POINTS


def test_validate_multi_chart():
    result = validate_chart_specs([
        {"id": 0, "chart_type": "bar", "title": "C1", "data": [{"name": "A", "value": 1}]},
        {"id": 1, "chart_type": "pie", "title": "C2", "data": [{"name": "B", "value": 2}]},
    ])
    assert len(result) == 2


def test_validate_truncates_long_strings():
    result = validate_chart_specs([{
        "id": 0,
        "chart_type": "bar",
        "title": "T" * 300,
        "description": "D" * 600,
        "x_axis_label": "X" * 200,
        "y_axis_label": "Y" * 200,
        "data": [{"name": "A", "value": 1}],
    }])
    assert len(result[0]["title"]) <= 200
    assert len(result[0]["description"]) <= 500
    assert len(result[0]["xAxisLabel"]) <= 100
    assert len(result[0]["yAxisLabel"]) <= 100
