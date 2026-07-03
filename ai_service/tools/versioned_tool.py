from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from tools.base import BaseTool


class ToolSchemaVersion(BaseModel):
    """A versioned tool schema descriptor.

    Attributes:
        version: Semantic version string (e.g. "1.0.0", "2.0.0").
        parameters: JSON Schema ``parameters`` dict for this version.
        deprecated_params: Parameter names that are deprecated in this version.
        migration_note: Human-readable migration guidance.
    """

    version: str
    parameters: dict[str, Any]
    deprecated_params: list[str] = []
    migration_note: str = ""


class VersionedTool(BaseTool):
    """Mixin for tools that support multiple schema versions.

    Subclasses MUST define ``schema_versions: list[ToolSchemaVersion]``.

    Usage::

        class MyTool(VersionedTool):
            schema_versions = [
                ToolSchemaVersion(version="1.0.0", parameters={...}),
                ToolSchemaVersion(version="2.0.0", parameters={...}),
            ]
    """

    schema_versions: list[ToolSchemaVersion] = []

    def get_schema(self, version: str | None = None) -> ToolSchemaVersion:
        """Return the requested schema version, or the latest if ``version`` is ``None``.

        Raises ``StopIteration`` if the requested version does not exist.
        """
        if version is None:
            return self.schema_versions[-1]
        return next(sv for sv in self.schema_versions if sv.version == version)
