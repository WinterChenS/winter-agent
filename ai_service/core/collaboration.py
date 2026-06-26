from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from core.agent_factory import AgentRuntime

logger = logging.getLogger(__name__)


class CollaborationResult:
    def __init__(self, content: str, agent_results: list[dict]) -> None:
        self.content = content
        self.agent_results = agent_results


class CollaborationEngine:
    async def execute(
        self,
        runtimes: list[AgentRuntime],
        user_query: str,
        strategy: str,
    ) -> CollaborationResult:
        if strategy == "sequential":
            return await self._sequential(runtimes, user_query)
        elif strategy == "parallel":
            return await self._parallel(runtimes, user_query)
        elif strategy == "supervisor":
            return await self._supervisor(runtimes, user_query)
        else:
            msg = f"Unknown strategy: {strategy}"
            raise ValueError(msg)

    async def _sequential(
        self,
        runtimes: list[AgentRuntime],
        user_query: str,
    ) -> CollaborationResult:
        context = user_query
        agent_results: list[dict[str, Any]] = []

        for runtime in runtimes:
            messages = [
                SystemMessage(content=runtime.system_prompt),
                HumanMessage(content=context),
            ]
            try:
                response = await runtime.llm.ainvoke(messages)
                content = response.content.strip()
                agent_results.append(
                    {"agent": runtime.name, "status": "ok", "output": content}
                )
                # Pass result to next agent
                context = (
                    f"Previous agent ({runtime.name}) result:\n{content}\n\n"
                    f"Original request: {user_query}"
                )
            except Exception as e:
                agent_results.append(
                    {"agent": runtime.name, "status": "error", "error": str(e)}
                )
                break

        final_content = (
            agent_results[-1].get("output", "")
            if agent_results
            else ""
        )
        return CollaborationResult(content=final_content, agent_results=agent_results)

    async def _parallel(
        self,
        runtimes: list[AgentRuntime],
        user_query: str,
    ) -> CollaborationResult:
        async def run_single(runtime):
            try:
                messages = [
                    SystemMessage(content=runtime.system_prompt),
                    HumanMessage(content=user_query),
                ]
                response = await runtime.llm.ainvoke(messages)
                return {"agent": runtime.name, "status": "ok", "output": response.content.strip()}
            except Exception as e:
                return {"agent": runtime.name, "status": "error", "error": str(e)}

        agent_results = await asyncio.gather(*[run_single(r) for r in runtimes], return_exceptions=True)

        # Handle exceptions from gather itself
        cleaned = []
        for r in agent_results:
            if isinstance(r, Exception):
                cleaned.append({"agent": "unknown", "status": "error", "error": str(r)})
            else:
                cleaned.append(r)

        # Merge results
        parts = []
        for r in cleaned:
            if r["status"] == "ok":
                parts.append(f"[{r['agent']}]: {r['output']}")
        merged = "\n\n".join(parts)

        return CollaborationResult(content=merged, agent_results=cleaned)

    async def _supervisor(
        self,
        runtimes: list[AgentRuntime],
        user_query: str,
    ) -> CollaborationResult:
        msg = "Supervisor strategy not yet implemented"
        raise NotImplementedError(msg)
