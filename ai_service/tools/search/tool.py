from __future__ import annotations

from typing import Mapping, Any

from tools.base import BaseTool, ToolResult


class SearchTool(BaseTool):
	name = "search"
	description = "Search the web for a query and return ranked snippets (mock in Week 3)."
	input_schema = {
		"type": "object",
		"properties": {
			"query": {"type": "string", "description": "Search query text"},
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
				"results": [
					{
						"title": "LangGraph Quickstart",
						"url": "https://example.com/langgraph-quickstart",
						"snippet": "Build a stateful graph with nodes, edges, and memory.",
					},
					{
						"title": "LangGraph ReAct Patterns",
						"url": "https://example.com/langgraph-react",
						"snippet": "Implement router-agent-tool loops with conditional edges.",
					},
					{
						"title": "LangGraph Checkpointer Guide",
						"url": "https://example.com/langgraph-checkpointer",
						"snippet": "Persist conversation state by thread_id for multi-turn runtime.",
					},
				],
			}
		)


