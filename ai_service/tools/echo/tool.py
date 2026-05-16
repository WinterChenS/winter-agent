from typing import Mapping, Any

from tools import BaseTool, ToolResult


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo input text back to caller (mock utility tool)."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Query to execute"},
        },
        "required": ["query"],
    }

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        query = str(input_payload.get("query", "")).strip()
        if not query:
            return ToolResult.failure(
                code="INVALID_INPUT",
                message="query is required and must be a non-empty string",
                retryable=False,
            )

        return ToolResult.success(
            {
                "query": query,
                "echo": query,
            }
        )
