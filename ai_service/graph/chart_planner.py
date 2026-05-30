from __future__ import annotations

import json
import logging

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

CHART_PLANNER_PROMPT = """\
You are a chart intent analyzer. Analyze the conversation and tool results to determine if a chart would help the user understand the data better.

**When a chart is needed:**
- Trend analysis (changes over time)
- Data comparison (rankings, benchmarks)
- Proportion analysis (percentages, composition)
- Growth rate analysis
- Stock/price movements
- AI model evaluation comparisons
- Any scenario with numerical data that benefits from visualization

**Chart type selection guide:**
- "line": Time series, trends over time, continuous data
- "bar": Category comparison, rankings, discrete groups
- "pie": Proportion, composition, share of total (use only when parts sum to a meaningful whole)
- "scatter": Correlation, distribution, relationship between two variables
- "area": Cumulative trends, volume over time
- "radar": Multi-dimensional comparison, spider/radar plots

**If NO chart is needed (simple facts, definitions, instructions), return need_chart: false.**

Respond with ONLY this JSON (no markdown):
{"need_chart": true, "chart_type": "bar", "reason": "comparing prices across 5 products"}
"""


async def plan_chart(
    llm: ChatOpenAI,
    user_message: str,
    tool_results_text: str,
) -> dict:
    """Analyze conversation and tool results to decide if a chart should be generated."""
    if not tool_results_text.strip():
        return {"need_chart": False, "chart_type": "", "reason": "no tool results to analyze"}

    messages = [
        SystemMessage(content=CHART_PLANNER_PROMPT),
        SystemMessage(content=f"User request: {user_message}"),
        SystemMessage(content=f"Tool results: {tool_results_text[:3000]}"),
        SystemMessage(content="Analyze and return ONLY the JSON."),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = (response.content or "").strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        parsed = json.loads(content)
        return {
            "need_chart": bool(parsed.get("need_chart", False)),
            "chart_type": str(parsed.get("chart_type", "")),
            "reason": str(parsed.get("reason", "")),
        }
    except Exception as exc:
        logger.warning("Chart planner failed: %s", exc)
        return {"need_chart": False, "chart_type": "", "reason": f"planner error: {exc}"}
