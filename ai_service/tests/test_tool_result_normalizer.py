from graph.normalizers.tool_result import (
    normalize_tool_result_for_prompt,
    normalize_tool_step_record,
)


def test_invalid_json_returns_safe_fallback():
    text = normalize_tool_result_for_prompt("not-json")
    assert text == "Tool returned data (sanitized)."


def test_time_tool_context():
    raw = '{"ok": true, "data": "2026-05-24 10:00:00"}'
    text = normalize_tool_result_for_prompt(raw)
    assert text.startswith("time:")
    assert "2026-05-24" in text


def test_search_result_compaction():
    raw = (
        '{"ok": true, "data": {'
        '"query": "杭州天气", '
        '"results": ['
        '{"title": "杭州天气预报", "url": "https://www.weather.com.cn/hz"},'
        '{"title": "今日杭州温度", "url": "https://example.com/a"}'
        ']}}'
    )
    text = normalize_tool_result_for_prompt(raw)
    assert "query: 杭州天气" in text
    assert "result_count: 2" in text
    assert "source=www.weather.com.cn" in text


def test_error_result_normalization():
    raw = '{"ok": false, "error": "bad request"}'
    text = normalize_tool_result_for_prompt(raw)
    assert text == "Tool execution failed: bad request"


def test_step_record_error_field_added_only_for_error():
    ok = normalize_tool_step_record("search", {"query": "a"}, "completed", 12, 1.2)
    bad = normalize_tool_step_record("search", {"query": "a"}, "error", 12, 1.2, error="boom")

    assert "error" not in ok
    assert bad["error"] == "boom"

