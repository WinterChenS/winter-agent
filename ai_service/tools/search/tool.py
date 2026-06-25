from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from functools import lru_cache
from typing import Any, Mapping

from tavily import TavilyClient

from tools.base import BaseTool, ToolResult
from tools.schema import tool, ToolSchema

logger = logging.getLogger(__name__)

# Cache configuration
_SEARCH_CACHE_MAX_SIZE = 100
_SEARCH_CACHE_TTL_SECONDS = 3600  # 1 hour

# Global cache for search results
_search_result_cache: dict[str, tuple[float, Any]] = {}


@tool
class SearchTool(BaseTool):
    name = "search"
    description = "Search the web for a query and return ranked snippets."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query text"},
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    }
    schema: ToolSchema = ToolSchema(
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        },
    )

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_api_key() -> str:
        """Cached retrieval of API key from environment."""
        return os.getenv("TAVILY_API_KEY", "").strip()

    @staticmethod
    def _get_cache_key(query: str, max_results: int) -> str:
        """Generate a cache key for the query."""
        key_str = f"{query}:{max_results}"
        return hashlib.md5(key_str.encode()).hexdigest()

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Normalize query for consistency."""
        return " ".join(query.split()).lower()

    @staticmethod
    def _is_cache_valid(timestamp: float) -> bool:
        """Check if a cached result is still valid."""
        import time
        return (time.time() - timestamp) < _SEARCH_CACHE_TTL_SECONDS

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        # Input validation
        query = str(input_payload.get("query", "")).strip()
        if not query:
            logger.warning("Search executed with empty query")
            return ToolResult.failure(
                code="INVALID_INPUT",
                message="query is required and must be a non-empty string",
                retryable=False,
            )

        if len(query) > 500:
            logger.warning(f"Search query exceeded max length: {len(query)}")
            return ToolResult.failure(
                code="INVALID_INPUT",
                message="query must be less than 500 characters",
                retryable=False,
            )

        max_results = input_payload.get("max_results", 5)
        try:
            max_results = int(max_results)
            if not 1 <= max_results <= 20:
                raise ValueError("max_results must be between 1 and 20")
        except (ValueError, TypeError):
            logger.warning(f"Invalid max_results value: {max_results}")
            max_results = 5

        # Check cache first
        normalized_query = self._normalize_query(query)
        cache_key = self._get_cache_key(normalized_query, max_results)

        if cache_key in _search_result_cache:
            timestamp, cached_data = _search_result_cache[cache_key]
            if self._is_cache_valid(timestamp):
                logger.info(f"Returning cached search results for query: {query}")
                return ToolResult.success(cached_data)
            else:
                # Remove expired cache entry
                del _search_result_cache[cache_key]

        # Retrieve API key
        api_key = self._get_api_key()
        if not api_key:
            logger.error("TAVILY_API_KEY environment variable not configured")
            return ToolResult.failure(
                code="MISSING_API_KEY",
                message="TAVILY_API_KEY is not configured",
                retryable=False,
            )

        try:
            logger.debug(f"Executing web search for query: {query}")
            client = TavilyClient(api_key=api_key)

            # TavilyClient.search is sync, run in a worker thread with timeout
            raw_result = await asyncio.wait_for(
                asyncio.to_thread(client.search, query=query, max_results=max_results),
                timeout=10.0,  # 10 second timeout
            )

            # Extract and validate results
            results = []
            if isinstance(raw_result, dict):
                raw_results = raw_result.get("results", [])
                # Filter and clean results
                for result in raw_results:
                    if isinstance(result, dict) and "url" in result:
                        results.append(
                            {
                                "title": result.get("title", ""),
                                "url": result.get("url", ""),
                                "content": result.get("content", ""),
                            }
                        )

            response_data = {
                "query": query,
                "count": len(results),
                "results": results,
            }

            # Cache the result (with size limit)
            if len(_search_result_cache) >= _SEARCH_CACHE_MAX_SIZE:
                # Simple eviction: remove oldest entry
                oldest_key = min(_search_result_cache.keys(), 
                               key=lambda k: _search_result_cache[k][0])
                del _search_result_cache[oldest_key]

            import time
            _search_result_cache[cache_key] = (time.time(), response_data)

            logger.info(f"Search completed successfully. Found {len(results)} results for query: {query}")
            return ToolResult.success(response_data)

        except asyncio.TimeoutError:
            logger.error(f"Search API call timed out for query: {query}")
            return ToolResult.failure(
                code="TIMEOUT",
                message="Search request timed out. Please try again.",
                retryable=True,
            )
        except ValueError as exc:
            logger.error(f"Invalid API response for query: {query} - {exc}")
            return ToolResult.failure(
                code="INVALID_RESPONSE",
                message="Received invalid response from search service",
                retryable=True,
            )
        except Exception as exc:
            logger.exception(f"Search tool execution failed for query: {query}")
            return ToolResult.failure(
                code="TOOL_EXECUTION_ERROR",
                message=f"search tool execution failed: {str(exc)[:100]}",
                retryable=True,
            )
