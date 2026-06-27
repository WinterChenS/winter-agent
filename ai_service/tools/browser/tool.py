from __future__ import annotations

import logging
import re
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from tools.base import BaseTool, ToolResult
from tools.schema import tool, ToolSchema

logger = logging.getLogger(__name__)

# Maximum content length returned to the LLM (tokens are expensive)
_MAX_TEXT_LENGTH = 8000
# Timeout for HTTP requests
_REQUEST_TIMEOUT = 15.0
# Maximum HTML size to parse (bytes)
_MAX_HTML_SIZE = 2 * 1024 * 1024  # 2 MB

# Tags to completely remove before text extraction
_REMOVE_TAGS = [
    "script", "style", "nav", "footer", "header",
    "aside", "noscript", "iframe", "form", "select",
    "button", "input", "textarea", "svg", "canvas",
]

# Candidate selectors for article/main content (tried in order)
_ARTICLE_SELECTORS = [
    "article",
    '[role="main"]',
    "main",
    ".post-content",
    ".article-content",
    ".entry-content",
    ".content",
    "#content",
    ".post-body",
    ".article-body",
]


@tool
class BrowserUseTool(BaseTool):
    name = "browser"
    description = (
        "Visit a URL and extract readable text content from the web page. "
        "Useful for reading articles, documentation, news, or any web page. "
        "Use this after searching to read the full content of a specific result."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full URL of the web page to visit and extract content from",
            },
            "extract_mode": {
                "type": "string",
                "enum": ["article", "full"],
                "description": "Extraction mode: 'article' tries to find the main content (default), 'full' extracts all visible text",
            },
        },
        "required": ["url"],
    }
    schema: ToolSchema = ToolSchema(
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL of the web page to visit and extract content from",
                },
                "extract_mode": {
                    "type": "string",
                    "enum": ["article", "full"],
                    "description": "Extraction mode: 'article' tries to find the main content (default), 'full' extracts all visible text",
                },
            },
            "required": ["url"],
        },
    )

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        url = str(input_payload.get("url") or input_payload.get("query") or "").strip()
        if not url:
            return ToolResult.failure(
                code="INVALID_INPUT",
                message="url is required and must be a non-empty string",
                retryable=False,
            )

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Validate URL format
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return ToolResult.failure(
                    code="INVALID_URL",
                    message=f"Cannot parse URL: {url}",
                    retryable=False,
                )
        except Exception:
            return ToolResult.failure(
                code="INVALID_URL",
                message=f"Invalid URL format: {url}",
                retryable=False,
            )

        extract_mode = str(input_payload.get("extract_mode", "article")).strip().lower()
        if extract_mode not in ("article", "full"):
            extract_mode = "article"

        # Headers to mimic a real browser
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    return ToolResult.failure(
                        code="NOT_HTML",
                        message=f"URL returned non-HTML content (type: {content_type[:60]})",
                        retryable=False,
                    )

                html = response.text[: _MAX_HTML_SIZE]
                if not html.strip():
                    return ToolResult.failure(
                        code="EMPTY_RESPONSE",
                        message="URL returned empty HTML content",
                        retryable=False,
                    )

        except httpx.HTTPStatusError as exc:
            logger.warning(f"HTTP error for {url}: {exc.response.status_code}")
            return ToolResult.failure(
                code="HTTP_ERROR",
                message=f"HTTP {exc.response.status_code} when fetching URL",
                retryable=True,
            )
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching {url}")
            return ToolResult.failure(
                code="TIMEOUT",
                message=f"Request timed out after {_REQUEST_TIMEOUT}s",
                retryable=True,
            )
        except httpx.RequestError as exc:
            logger.warning(f"Request error for {url}: {exc}")
            return ToolResult.failure(
                code="REQUEST_ERROR",
                message=f"Failed to fetch URL: {str(exc)[:150]}",
                retryable=True,
            )
        except Exception as exc:
            logger.exception(f"Unexpected error fetching {url}")
            return ToolResult.failure(
                code="FETCH_ERROR",
                message=f"Unexpected error fetching URL: {str(exc)[:150]}",
                retryable=True,
            )

        try:
            soup = BeautifulSoup(html, "lxml")

            title = _extract_title(soup)
            text = _extract_content(soup, extract_mode)

            if not text.strip():
                return ToolResult.failure(
                    code="NO_CONTENT",
                    message="No readable text content found on the page",
                    retryable=False,
                )

            # Truncate to max length with a note
            original_length = len(text)
            if original_length > _MAX_TEXT_LENGTH:
                text = text[:_MAX_TEXT_LENGTH] + f"\n\n[Content truncated: {original_length - _MAX_TEXT_LENGTH} more characters]"

            return ToolResult.success({
                "url": str(response.url),
                "title": title,
                "text": text,
                "length": original_length,
            })

        except Exception as exc:
            logger.exception(f"Error parsing HTML from {url}")
            return ToolResult.failure(
                code="PARSE_ERROR",
                message=f"Error parsing page content: {str(exc)[:150]}",
                retryable=False,
            )


def _extract_title(soup: BeautifulSoup) -> str:
    """Extract the page title."""
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)[:200]
    return "Untitled"


def _extract_content(soup: BeautifulSoup, mode: str) -> str:
    """Extract readable text content from the page."""
    # Remove unwanted tags
    for tag_name in _REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    if mode == "article":
        article_soup = _find_article_container(soup)

        if article_soup is not None:
            return _clean_text(article_soup.get_text("\n", strip=True))

        return _clean_text(soup.get_text("\n", strip=True))

    # full mode: extract all text from body
    body = soup.find("body")
    if body:
        return _clean_text(body.get_text("\n", strip=True))
    return _clean_text(soup.get_text("\n", strip=True))


def _find_article_container(soup: BeautifulSoup) -> BeautifulSoup | None:
    """Try to find the main article/content container using common selectors."""
    for selector in _ARTICLE_SELECTORS:
        match = soup.select_one(selector)
        if match:
            text_len = len(match.get_text(strip=True))
            if text_len > 100:
                return match

    # Fallback: find the largest text block in <p> tags
    paragraphs = soup.find_all("p")
    if not paragraphs:
        return None

    best_parent = None
    best_score = 0
    for p in paragraphs:
        parent = p.find_parent()
        if parent is None:
            continue
        p_tags = len(parent.find_all("p"))
        text_len = len(parent.get_text(strip=True))
        score = p_tags * 10 + min(text_len, 5000)
        if score > best_score:
            best_score = score
            best_parent = parent

    if best_parent and best_score > 20:
        return best_parent
    return None


def _clean_text(text: str) -> str:
    """Clean extracted text: collapse whitespace and remove empty lines."""
    # Collapse multiple whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Remove lines that are just whitespace
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    # Remove repeated empty lines
    result = "\n".join(lines)
    # Collapse 3+ newlines into 2
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result
