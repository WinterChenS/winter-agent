from __future__ import annotations

import json
import logging

from langchain_openai import ChatOpenAI

from config import settings
from models.agent import AgentDefinition
from repositories.agent_repository import AgentRepository

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """You are an intent router. Given a user query and available agents, select the best agent(s).

Available agents:
{agent_descriptions}

Output a JSON object with:
- "agents": list of agent names (1-3)
- "strategy": "sequential" | "parallel" | "supervisor"

Rules:
- If the question is simple, use 1 agent with "sequential" strategy
- If the question needs multiple perspectives, use multiple agents with "parallel"
- If the question is complex and needs coordination, use "supervisor"
- NEVER select more than 3 agents
- Output ONLY the JSON object, no explanation
"""


class RouterResult:
    def __init__(
        self,
        agents: list[AgentDefinition],
        strategy: str,
        source: str,
    ) -> None:
        self.agents = agents
        self.strategy = strategy
        self.source = source  # "keyword" or "llm"


class RouterAgent:
    def __init__(self, repository: AgentRepository) -> None:
        self._repo = repository

    async def route(self, user_query: str) -> RouterResult:
        agents = await self._repo.list_enabled()
        if not agents:
            return RouterResult([], "sequential", "none")

        # 1. Keyword matching
        matched = self._keyword_match(user_query, agents)
        if matched:
            strategy = (
                matched[0].collaboration_strategy
                if len(matched) == 1
                else "parallel"
            )
            return RouterResult(matched, strategy, "keyword")

        # 2. LLM fallback
        return await self._llm_route(user_query, agents)

    def _keyword_match(
        self,
        query: str,
        agents: list[AgentDefinition],
    ) -> list[AgentDefinition]:
        query_lower = query.lower()
        scored: list[tuple[AgentDefinition, int]] = []
        for agent in agents:
            if not agent.trigger_keywords:
                continue
            hits = sum(1 for kw in agent.trigger_keywords if kw.lower() in query_lower)
            if hits > 0:
                scored.append((agent, hits))
        scored.sort(key=lambda x: (-x[1], -x[0].priority))
        # Return top 3
        return [a for a, _ in scored[:3]]

    async def _llm_route(
        self,
        query: str,
        agents: list[AgentDefinition],
    ) -> RouterResult:
        descriptions = "\n".join(
            [
                f"- {a.name}: {a.description} (strategy: {a.collaboration_strategy})"
                for a in agents
            ]
        )
        prompt = ROUTER_SYSTEM_PROMPT.format(agent_descriptions=descriptions)
        llm = ChatOpenAI(
            model=settings.model,
            temperature=0,
            api_key=settings.api_key,
            base_url=settings.base_url,
        )
        response = await llm.ainvoke(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": query},
            ]
        )
        try:
            result = json.loads(response.content)
            names = result.get("agents", [])[:3]
            strategy = result.get("strategy", "sequential")
            selected = [a for a in agents if a.name in names]
            if not selected:
                return RouterResult(agents[:1], "sequential", "llm")
            return RouterResult(selected, strategy, "llm")
        except Exception:
            return RouterResult(agents[:1], "sequential", "llm")
