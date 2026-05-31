from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

BlockType = Literal["markdown", "chart", "table", "code"]


@dataclass(slots=True)
class ContentBlock:
    type: BlockType
    content: str = ""
    chart_id: str = ""
    chart_spec: dict[str, Any] | None = None
    language: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type}
        if self.type == "markdown":
            d["content"] = self.content
        elif self.type == "chart":
            d["chartId"] = self.chart_id
            if self.chart_spec:
                d["chartSpec"] = self.chart_spec
        elif self.type == "code":
            d["content"] = self.content
            d["language"] = self.language
        elif self.type == "table":
            d["content"] = self.content
        return d
