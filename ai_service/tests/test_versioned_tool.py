from __future__ import annotations

from typing import Any, Mapping

import pytest

from tools.base import BaseTool, ToolResult
from tools.schema import ToolSchema
from tools.versioned_tool import ToolSchemaVersion, VersionedTool


class _VersionedTimeTool(VersionedTool):
    name: str = "time"
    description: str = "Get current time"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "timezone": {"type": "string", "description": "Timezone name"},
        },
    }
    schema: ToolSchema = ToolSchema(parameters={"type": "object", "properties": {"timezone": {"type": "string"}}})
    schema_versions: list[ToolSchemaVersion] = [
        ToolSchemaVersion(
            version="1.0.0",
            parameters={"type": "object", "properties": {"timezone": {"type": "string"}}},
            deprecated_params=[],
            migration_note="Initial version",
        ),
        ToolSchemaVersion(
            version="2.0.0",
            parameters={
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "IANA timezone name"},
                    "format": {"type": "string", "description": "Output format (full/short)"},
                },
                "required": [],
            },
            deprecated_params=["timezone"],
            migration_note="Added format parameter; timezone is now optional",
        ),
    ]

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data={"time": "2026-07-03 12:00:00"})


class TestToolSchemaVersion:
    def test_schema_version_creation(self):
        """ToolSchemaVersion 应正确存储版本号与参数。"""
        sv = ToolSchemaVersion(version="1.0.0", parameters={"type": "object", "properties": {}})
        assert sv.version == "1.0.0"
        assert sv.parameters == {"type": "object", "properties": {}}
        assert sv.deprecated_params == []
        assert sv.migration_note == ""

    def test_schema_version_with_all_fields(self):
        """ToolSchemaVersion 应接受所有可选字段。"""
        sv = ToolSchemaVersion(
            version="2.0.0",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            deprecated_params=["x"],
            migration_note="x is deprecated",
        )
        assert sv.deprecated_params == ["x"]
        assert sv.migration_note == "x is deprecated"


class TestVersionedTool:
    def test_get_schema_returns_latest_by_default(self):
        """get_schema() 默认返回最新版本。"""
        tool = _VersionedTimeTool()
        schema = tool.get_schema()
        assert schema.version == "2.0.0"
        assert "format" in schema.parameters["properties"]

    def test_get_schema_specific_version(self):
        """get_schema('1.0.0') 应返回指定版本。"""
        tool = _VersionedTimeTool()
        schema = tool.get_schema("1.0.0")
        assert schema.version == "1.0.0"
        assert "format" not in schema.parameters["properties"]

    def test_get_schema_unknown_version_raises_value_error(self):
        """请求不存在的版本应抛出 ValueError。"""
        tool = _VersionedTimeTool()
        with pytest.raises(ValueError, match="not found"):
            tool.get_schema("9.9.9")

    def test_get_schema_empty_versions_raises(self):
        """没有 schema_versions 时应抛出 ValueError。"""
        class _EmptyVersionedTool(VersionedTool):
            name: str = "empty"
            description: str = "Empty tool"
            input_schema: dict = {}
            schema: ToolSchema = ToolSchema(parameters={})
            schema_versions: list[ToolSchemaVersion] = []

            async def execute(self, input_payload):
                return ToolResult.success(data={})

        tool = _EmptyVersionedTool()
        with pytest.raises(ValueError, match="No schema versions available"):
            tool.get_schema()

    def test_deprecated_params_listed(self):
        """deprecated_params 应列出已弃用的参数。"""
        tool = _VersionedTimeTool()
        schema = tool.get_schema("2.0.0")
        assert "timezone" in schema.deprecated_params
