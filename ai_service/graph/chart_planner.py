from __future__ import annotations

import json
import logging

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

CHART_PLANNER_PROMPT = """\
You are a chart intent analyzer. Analyze the conversation to determine what charts the user needs.

**When charts are needed:**
- Trend analysis (changes over time) → line/area chart
- Data comparison (rankings, benchmarks) → bar chart
- Proportion analysis (percentages, composition) → pie chart
- Correlation or distribution → scatter chart
- Multi-dimensional comparison → radar chart
- Stock/price movements → line chart
- Any numerical data that benefits from visualization

**You MUST generate one chart per distinct data topic.** For example:
- "Compare stock prices AND show investor ratios" → TWO charts (line + pie)
- "Show sales trend" → ONE chart (line)
- Simple facts with no data → ZERO charts

**Respond with ONLY this JSON (no markdown):**
{"charts": [
  {"chart_type": "line", "reason": "stock price trend over time"},
  {"chart_type": "pie", "reason": "investor ratio distribution"}
]}

If no chart is needed, return: {"charts": []}
"""


async def plan_charts(
    llm: ChatOpenAI,
    user_message: str,
    tool_results_text: str,
) -> list[dict]:
    """Analyze conversation and tool results to determine what charts to generate.

    Returns a list of chart intent dicts: [{"chart_type": "line", "reason": "..."}, ...]
    """
    if not tool_results_text.strip():
        return []

    messages = [
        SystemMessage(content=CHART_PLANNER_PROMPT),
        SystemMessage(content=f"User request: {user_message}"),
        SystemMessage(content=f"Available data: {tool_results_text[:3000]}"),
        SystemMessage(content="Analyze and return ONLY the JSON with 'charts' array."),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = (response.content or "").strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        parsed = json.loads(content)

        # Support both new format {"charts": [...]} and legacy format {"need_chart": ...}
        if "charts" in parsed:
            charts = parsed["charts"]
            if isinstance(charts, list):
                return [
                    {
                        "chart_type": str(c.get("chart_type", "bar")),
                        "reason": str(c.get("reason", "")),
                    }
                    for c in charts
                    if c.get("chart_type")
                ]
            return []

        # Legacy single-chart format fallback
        if parsed.get("need_chart"):
            return [{
                "chart_type": str(parsed.get("chart_type", "bar")),
                "reason": str(parsed.get("reason", "")),
            }]
        return []

    except Exception as exc:
        logger.warning("Chart planner failed: %s", exc)
        return []
