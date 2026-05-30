from __future__ import annotations

import pytest

from domain.capability import CapabilityCall
from tools.base import BaseTool, ToolResult
from tools.registry import ToolRegistry


class _EchoTool(BaseTool):
    name = "echo"
    description = "Echo back query"
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}}}

    async def execute(self, input_payload):
        return ToolResult.success({"query": input_payload.get("query", "")})


@pytest.mark.asyncio
async def test_tool_to_capability_projection():
    registry = ToolRegistry()
    registry.register(_EchoTool())

    caps = registry.list_capabilities()
    assert len(caps) == 1
    assert caps[0]["name"] == "echo"
    assert caps[0]["kind"] == "tool"


@pytest.mark.asyncio
async def test_invoke_capability_success():
    registry = ToolRegistry()
    registry.register(_EchoTool())

    call = CapabilityCall(capability_name="echo", input_payload={"query": "hello"})
    result = await registry.invoke_capability(call)

    assert result["ok"] is True
    assert result["data"]["query"] == "hello"


@pytest.mark.asyncio
async def test_unknown_capability_returns_standard_error():
    registry = ToolRegistry()

    call = CapabilityCall(capability_name="missing", input_payload={"query": "x"})
    result = await registry.invoke_capability(call)

    assert result["ok"] is False
    assert result["error"]["code"] == "CAPABILITY_NOT_FOUND"

