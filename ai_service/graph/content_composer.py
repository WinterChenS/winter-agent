from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from domain.content_block import ContentBlock

logger = logging.getLogger(__name__)

COMPOSER_PROMPT = """\
You are a content organizer. Given a text answer and chart specifications, split the answer into ordered blocks.

**Block types:**
- "markdown": A paragraph or section of markdown text
- "chart": A chart visualization (referenced by index in the charts list)
- "table": A markdown table
- "code": A code block

**Rules:**
1. Split at natural paragraph/section boundaries
2. Place "chart" blocks right AFTER the text that introduces them
3. Use chart index from the charts list (0-based)
4. Keep markdown blocks reasonably sized (not one huge block)

**Output ONLY this JSON array:**
[
  {"type": "markdown", "content": "intro paragraph..."},
  {"type": "chart", "chartIndex": 0},
  {"type": "markdown", "content": "more analysis..."},
  {"type": "chart", "chartIndex": 1}
]
"""


async def compose_blocks(
    llm: ChatOpenAI,
    user_message: str,
    answer_text: str,
    chart_specs: list[dict],
) -> list[dict]:
    """Organize the answer text and chart specs into ordered content blocks."""
    if not answer_text.strip():
        # No answer text — just emit charts as blocks
        blocks = []
        for i, cs in enumerate(chart_specs):
            blocks.append({
                "type": "chart",
                "chart_index": i,
            })
        return blocks

    if not chart_specs:
        return [{"type": "markdown", "content": answer_text}]

    # Describe charts to the LLM
    charts_desc = ""
    for i, cs in enumerate(chart_specs):
        charts_desc += f"  Chart {i}: type={cs.get('chartType','?')}, title='{cs.get('title','')}', points={len(cs.get('data',[]))}\n"

    messages = [
        SystemMessage(content=COMPOSER_PROMPT),
        SystemMessage(content=f"User asked: {user_message}"),
        SystemMessage(content=f"Available charts:\n{charts_desc}"),
        SystemMessage(content=f"Answer text to organize:\n{answer_text}"),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = (response.content or "").strip()
        if content.startswith("```"): content = _unwrap_fence(content)
        blocks_raw = json.loads(content)

        if not isinstance(blocks_raw, list):
            return _fallback_blocks(answer_text, chart_specs)

        blocks = []
        for i, b in enumerate(blocks_raw):
            if not isinstance(b, dict):
                continue
            btype = b.get("type", "markdown")
            if btype == "chart":
                idx = int(b.get("chartIndex", 0))
                if idx < len(chart_specs):
                    blocks.append({
                        "type": "chart",
                        "chart_index": idx,
                        "chart_spec": chart_specs[idx],
                    })
            elif btype == "markdown":
                blocks.append({"type": "markdown", "content": b.get("content", "")})
            elif btype == "table":
                blocks.append({"type": "table", "content": b.get("content", "")})
            elif btype == "code":
                blocks.append({"type": "code", "content": b.get("content", ""), "language": b.get("language", "")})
        return blocks or _fallback_blocks(answer_text, chart_specs)

    except Exception as exc:
        logger.warning("Content composer failed: %s, using fallback", exc)
        return _fallback_blocks(answer_text, chart_specs)


def _unwrap_fence(text: str) -> str:
    parts = text.split("```")
    if len(parts) >= 2:
        return parts[1].removeprefix("json").strip()
    return text


def _fallback_blocks(answer: str, chart_specs: list[dict]) -> list[dict]:
    """Fallback: split answer by double newlines, intersperse charts at the end."""
    blocks = []
    paragraphs = re.split(r"\n\n+", answer)
    for p in paragraphs:
        p = p.strip()
        if p:
            blocks.append({"type": "markdown", "content": p})

    for cs in chart_specs:
        blocks.append({"type": "chart", "chart_spec": cs})
    return blocks
