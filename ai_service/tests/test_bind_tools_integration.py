from __future__ import annotations

from typing import Any, Mapping
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.base import BaseTool, ToolResult
from tools.schema import ToolSchema
from tools.schema_adapter import ToolSchemaAdapter


class _MockSearchTool(BaseTool):
    name: str = "search"
    description: str = "Web search"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"],
    }
    schema: ToolSchema = ToolSchema(parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data={"result": f"found: {input_payload.get('query')}"})


class TestProviderFallbackJsonMode:
    """验证 provider 不支持 tool_calls 时降级到 JSON Mode。"""

    @patch("graph.nodes.get_tool_registry")
    @patch("graph.nodes._build_llm")
    async def test_fallback_to_json_mode_when_provider_unsupported(self, mock_build_llm, mock_get_registry):
        """当 provider 不支持 tool_calls 时，应降级到 JSON Mode。"""
        from graph.nodes import agent_node

        mock_llm = AsyncMock()
        mock_response = AsyncMock()
        mock_response.content = '{"action": "tool", "tool": "search", "query": "test"}'
        mock_response.tool_calls = None
        mock_llm.ainvoke.return_value = mock_response
        mock_build_llm.return_value = mock_llm

        mock_reg = MagicMock()
        mock_reg.list_tools.return_value = [{"name": "search", "description": "Web search", "input_schema": {}}]
        mock_get_registry.return_value = mock_reg

        # Simulate provider not supporting tool_calls by patching settings
        import graph.nodes as nodes
        with patch("graph.nodes.settings") as mock_settings:
            mock_settings.provider_supports_tool_calls = False
            state = {
                "messages": [],
                "iteration_count": 0,
                "consecutive_search_count": 0,
                "tool_steps": [],
                "reasoning_steps": [],
                "active_agent": "default",
            }
            result = await agent_node(state)
            assert result["route"] == "tool"
            assert result.get("current_tool") == "search"


class TestAgentNodeToolCallsRouting:
    """验证 agent_node 对 AIMessage.tool_calls 的路由逻辑。"""

    @patch("graph.nodes.get_tool_registry")
    @patch("graph.nodes._build_llm")
    async def test_routes_to_tool_when_tool_calls_present(self, mock_build_llm, mock_get_registry):
        """当 LLM 返回 tool_calls 时，路由应为 'tool'。"""
        from graph.nodes import agent_node

        mock_llm = AsyncMock()
        mock_response = AsyncMock()
        mock_response.content = ""
        mock_response.tool_calls = [
            {"id": "call_1", "name": "search", "args": {"query": "test"}}
        ]
        mock_llm.ainvoke.return_value = mock_response
        mock_build_llm.return_value = mock_llm

        mock_reg = MagicMock()
        mock_reg.list_tools.return_value = [
            {"name": "search", "description": "Web search", "input_schema": {}}
        ]
        mock_reg.get.return_value = _MockSearchTool()
        mock_get_registry.return_value = mock_reg

        state = {
            "messages": [],
            "iteration_count": 0,
            "consecutive_search_count": 0,
            "tool_steps": [],
            "reasoning_steps": [],
            "active_agent": "default",
        }
        result = await agent_node(state)
        assert result["route"] == "tool"

    @patch("graph.nodes.get_tool_registry")
    @patch("graph.nodes._build_llm")
    async def test_routes_to_chart_planner_when_no_tool_calls(self, mock_build_llm, mock_get_registry):
        """当 LLM 无 tool_calls 且已有 tool_result 时，路由应为 'chart_planner'。"""
        from graph.nodes import agent_node

        mock_llm = AsyncMock()
        mock_response = AsyncMock()
        mock_response.content = "Final answer."
        mock_response.tool_calls = None
        mock_llm.ainvoke.return_value = mock_response
        mock_build_llm.return_value = mock_llm

        mock_reg = MagicMock()
        mock_reg.list_tools.return_value = [{"name": "search", "description": "Web search", "input_schema": {}}]
        mock_reg.get.return_value = _MockSearchTool()
        mock_get_registry.return_value = mock_reg

        state = {
            "messages": [],
            "iteration_count": 1,
            "consecutive_search_count": 0,
            "tool_steps": [{"tool": "search", "status": "completed"}],
            "reasoning_steps": [],
            "tool_result": '{"ok": true, "data": {"results": []}}',
            "active_agent": "default",
        }
        result = await agent_node(state)
        assert result["route"] == "chart_planner"
