from __future__ import annotations

import pytest
from pydantic import ValidationError

from tools.schema import ToolSchema, tool


class TestToolSchema:
    def test_accepts_valid_parameters(self):
        """ToolSchema(parameters={...}) 应当接受合法的 parameters"""
        schema = ToolSchema(parameters={"type": "object", "properties": {}})
        assert schema.parameters == {"type": "object", "properties": {}}

    def test_raises_error_when_parameters_missing(self):
        """当 parameters 缺失时应当抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ToolSchema()  # type: ignore[call-arg]


class TestToolDecorator:
    def test_sets_is_tool_true(self):
        """@tool 装饰器应当设置 _is_tool = True"""

        @tool
        class MyTool:
            pass

        assert MyTool._is_tool is True

    def test_class_with_decorator_has_is_tool(self):
        """带 @tool 的类应当有 _is_tool = True"""

        @tool
        class AnotherTool:
            pass

        assert hasattr(AnotherTool, "_is_tool")
        assert AnotherTool._is_tool is True

    def test_class_without_decorator_does_not_have_is_tool(self):
        """不带 @tool 的类不应当有 _is_tool 属性"""

        class PlainClass:
            pass

        assert not hasattr(PlainClass, "_is_tool")
