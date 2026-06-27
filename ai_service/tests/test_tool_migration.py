from __future__ import annotations

import asyncio

from tools.browser.tool import BrowserUseTool
from tools.registry import ToolRegistry
from tools.search.tool import SearchTool
from tools.time.tool import TimeTool


class TestSearchToolMigration:
    """SearchTool 必须被 @tool 装饰并拥有 schema。"""

    def test_search_tool_class_has_is_tool(self):
        """SearchTool 类应有 _is_tool = True（由 @tool 装饰器设置）。"""
        assert hasattr(SearchTool, "_is_tool")
        assert SearchTool._is_tool is True

    def test_search_tool_instance_has_schema_with_query(self):
        """SearchTool 实例应有 schema，且包含 query 参数。"""
        tool = SearchTool()
        assert tool.schema is not None
        props = tool.schema.parameters.get("properties", {})
        assert "query" in props


class TestTimeToolMigration:
    """TimeTool 必须被 @tool 装饰。"""

    def test_time_tool_class_has_is_tool(self):
        """TimeTool 类应有 _is_tool = True（由 @tool 装饰器设置）。"""
        assert hasattr(TimeTool, "_is_tool")
        assert TimeTool._is_tool is True


class TestBrowserUseToolMigration:
    """BrowserUseTool 必须被 @tool 装饰。"""

    def test_browser_tool_class_has_is_tool(self):
        """BrowserUseTool 类应有 _is_tool = True（由 @tool 装饰器设置）。"""
        assert hasattr(BrowserUseTool, "_is_tool")
        assert BrowserUseTool._is_tool is True


class TestToolDiscovery:
    """ToolRegistry.discover() 应能自动发现所有 migrated 工具。"""

    def test_discover_auto_discovers_all_three_tools(self):
        """discover() 应注册 search / time / browser 三个工具。"""
        registry = ToolRegistry()
        registry.discover()
        names = [t["name"] for t in registry.list_tools()]
        assert "search" in names
        assert "time" in names
        assert "browser" in names


class TestToolExecution:
    """所有 migrated 工具应可正常执行（简单 invoke 测试）。"""

    def test_search_executes_with_empty_query(self):
        """SearchTool 传入空 query 应返回失败（不抛出异常）。"""
        tool = SearchTool()
        result = asyncio.run(tool.execute({"query": ""}))
        assert result.ok is False

    def test_time_executes_without_params(self):
        """TimeTool 不传参数应返回当前时间字符串。"""
        tool = TimeTool()
        result = asyncio.run(tool.execute({}))
        assert result.ok is True
        assert isinstance(result.data, str)

    def test_browser_executes_without_url(self):
        """BrowserUseTool 不传 url 应返回失败（不抛出异常）。"""
        tool = BrowserUseTool()
        result = asyncio.run(tool.execute({}))
        assert result.ok is False
