from __future__ import annotations
import logging
from typing import Any, Mapping
from tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

class OutputTextTool(BaseTool):
    name = "output_text"
    description = "Output a markdown text block to the user. Use this to show partial analysis results as you work — call this BETWEEN data analysis steps so the user sees your progress in real-time. Then continue with more tools or give Final Answer."
    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "description": "The markdown text to output as a content block"}
        }
    }

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        text = str(input_payload.get("query", "")).strip()
        if not text:
            return ToolResult.failure("EMPTY_TEXT", "query must be non-empty text", retryable=False)
        return ToolResult.success({"text": text})
