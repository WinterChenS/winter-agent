from __future__ import annotations

import asyncio
import json
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
        if len(runtimes) < 2:
            # Fall back to sequential with just the one agent
            return await self._sequential(runtimes, user_query)

        supervisor = runtimes[0]
        workers = runtimes[1:]
        agent_results: list[dict[str, Any]] = []

        # Step 1: Supervisor decomposes the task
        decompose_prompt = f"""You are a task supervisor. Decompose this user request into subtasks for workers.

User request: {user_query}

Available workers: {', '.join([w.name for w in workers])}

Output a JSON array of subtasks:
[{{"worker": "worker_name", "task": "specific task description"}}]

Rules:
- Assign each subtask to the most appropriate worker
- Each worker should get at most one task
- Keep it concise — output ONLY the JSON array
"""
        try:
            response = await supervisor.llm.ainvoke([
                SystemMessage(content=supervisor.system_prompt),
                HumanMessage(content=decompose_prompt),
            ])
            subtasks = json.loads(response.content.strip())
        except Exception:
            # Fallback: run workers in parallel on the original query
            return await self._parallel(runtimes, user_query)

        # Step 2: Execute subtasks in parallel
        worker_map = {w.name: w for w in workers}

        async def run_worker(task_info):
            worker_name = task_info.get("worker", "")
            task = task_info.get("task", user_query)
            worker = worker_map.get(worker_name)
            if not worker:
                return {"agent": worker_name, "status": "error", "error": "Worker not found"}
            try:
                response = await worker.llm.ainvoke([
                    SystemMessage(content=worker.system_prompt),
                    HumanMessage(content=task),
                ])
                return {"agent": worker_name, "status": "ok", "output": response.content.strip()}
            except Exception as e:
                return {"agent": worker_name, "status": "error", "error": str(e)}

        worker_results = await asyncio.gather(*[run_worker(t) for t in subtasks], return_exceptions=True)

        # Clean results
        cleaned = []
        for r in worker_results:
            if isinstance(r, Exception):
                cleaned.append({"agent": "unknown", "status": "error", "error": str(r)})
            else:
                cleaned.append(r)

        agent_results = [{"agent": supervisor.name, "status": "ok", "output": f"Decomposed into {len(subtasks)} subtasks"}]
        agent_results.extend(cleaned)

        # Step 3: Supervisor synthesizes final answer
        worker_outputs = "\n".join([
            f"[{r['agent']}]: {r.get('output', r.get('error', ''))}"
            for r in cleaned
        ])

        synthesize_prompt = f"""Based on the worker results below, provide the final answer to the user.

Original request: {user_query}

Worker results:
{worker_outputs}

Provide a comprehensive final answer that synthesizes all the results."""

        try:
            response = await supervisor.llm.ainvoke([
                SystemMessage(content=supervisor.system_prompt),
                HumanMessage(content=synthesize_prompt),
            ])
            final_content = response.content.strip()
        except Exception:
            final_content = worker_outputs

        return CollaborationResult(content=final_content, agent_results=agent_results)
