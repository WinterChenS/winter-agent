from __future__ import annotations

import json
import logging

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from domain.chart_spec import CHART_SPEC_JSON_SCHEMA, ChartSpec

logger = logging.getLogger(__name__)

CHART_GENERATOR_PROMPT = f"""\
You are a chart data generator. Given user request, tool results, and chart intent, generate structured chart data.

**Output format** — respond with ONLY this JSON (no markdown, no extra text):
{json.dumps(CHART_SPEC_JSON_SCHEMA, indent=2)}

**Rules:**
1. Extract numerical data from tool results
2. Use descriptive names for data points
3. Values must be actual numbers from the data (not invented)
4. Use the "group" field for multi-series charts (e.g., different models, categories)
5. Include axis labels when meaningful
"""


async def generate_chart_spec(
    llm: ChatOpenAI,
    user_message: str,
    tool_results_text: str,
    chart_intent: dict,
) -> dict | None:
    """Generate a ChartSpec dict from conversation context and chart intent."""
    chart_type = chart_intent.get("chart_type", "")
    if not chart_type:
        return None

    messages = [
        SystemMessage(content=CHART_GENERATOR_PROMPT),
        SystemMessage(content=f"User request: {user_message}"),
        SystemMessage(content=f"Tool results (extract numbers from here):\n{tool_results_text[:4000]}"),
        SystemMessage(content=f"Generate a '{chart_type}' chart. Reason: {chart_intent.get('reason', '')}"),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = (response.content or "").strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        parsed = json.loads(content)
        spec = ChartSpec.from_dict(parsed)
        spec.chart_type = chart_type
        return spec.to_dict()
    except Exception as exc:
        logger.warning("Chart generator failed: %s", exc)
        return None
