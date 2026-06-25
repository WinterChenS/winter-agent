from __future__ import annotations

import asyncio

import pytest

from tools.registry import ToolRegistry


def _ensure_tools_loaded():
    """Import tool modules so BaseTool.__subclasses__() finds them."""
    import tools.search.tool  # noqa: F401
    import tools.time.tool  # noqa: F401
    import tools.browser.tool  # noqa: F401
    import tools.sandbox.tool  # noqa: F401


@pytest.mark.asyncio
async def test_full_pipeline_discover_and_invoke():
    """E2E: discover -> prompt -> single invoke -> parallel invoke -> error isolation."""
    _ensure_tools_loaded()
    registry = ToolRegistry()
    registry.discover()

    # 1. All 4 tools discovered
    tools = registry.list_tools()
    tool_names = {t["name"] for t in tools}
    assert tool_names >= {"search", "time", "browser", "code_sandbox"}

    # 2. Prompt includes tool descriptions
    prompt = registry.build_tools_prompt()
    assert "search" in prompt
    assert "time" in prompt
    assert "code_sandbox" in prompt

    # 3. Single invoke works (time tool is fast and needs no API key)
    result = await registry.invoke("time", {})
    assert result["ok"] is True

    # 4. Code sandbox works
    result = await registry.invoke("code_sandbox", {"code": "print(42)"})
    assert result["ok"] is True
    assert "42" in str(result.get("data", {}).get("output", ""))

    # 5. Parallel invoke works for 2 simultaneous calls (time + sandbox)
    time_result, sandbox_result = await asyncio.gather(
        registry.invoke("time", {}),
        registry.invoke("code_sandbox", {"code": "print(99)"}),
    )
    assert time_result["ok"] is True
    assert sandbox_result["ok"] is True
    assert "99" in str(sandbox_result.get("data", {}).get("output", ""))

    # 6. Error isolation: one tool fails, another succeeds in parallel
    # code_sandbox with empty code fails with INVALID_INPUT,
    # while time still succeeds independently
    sandbox_fail, time_result2 = await asyncio.gather(
        registry.invoke("code_sandbox", {}),
        registry.invoke("time", {}),
    )
    assert sandbox_fail["ok"] is False
    error = sandbox_fail.get("error", {})
    assert error.get("code") == "INVALID_INPUT"
    # time should succeed independently despite the parallel failure
    assert time_result2["ok"] is True
