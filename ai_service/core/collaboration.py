from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from core.agent_factory import AgentRuntime
from core.streaming_event_bus import StreamingEventBus

logger = logging.getLogger(__name__)


class CollaborationResult:
    def __init__(self, content: str, agent_results: list[dict],
                 chart_specs: list[dict] | None = None) -> None:
        self.content = content
        self.agent_results = agent_results
        self.chart_specs = chart_specs or []


def _build_lc_tool(tool_obj):
    """Build a LangChain StructuredTool from a BaseTool, using its input_schema."""
    from langchain_core.tools import StructuredTool

    name = tool_obj.name
    desc = getattr(tool_obj, 'description', name) or name
    input_schema = getattr(tool_obj, 'input_schema', None) or {}

    async def _execute(**kwargs) -> str:
        # Unwrap if LangChain double-wraps in 'kwargs' key
        if 'kwargs' in kwargs and len(kwargs) == 1:
            kwargs = kwargs['kwargs']
        result = await tool_obj.execute(kwargs)
        return str(result)

    return StructuredTool(
        name=name,
        description=desc,
        func=None,
        coroutine=_execute,
        args_schema=input_schema,
    )


class CollaborationEngine:
    def __init__(self, event_bus: StreamingEventBus | None = None) -> None:
        self._bus = event_bus

    def _emit(self, event_type: str, **data: Any) -> None:
        if self._bus:
            self._bus.emit(event_type, **data)

    async def execute(
        self,
        runtimes: list[AgentRuntime],
        user_query: str,
        strategy: str,
    ) -> CollaborationResult:
        if strategy == "sequential":
            result = await self._sequential(runtimes, user_query)
        elif strategy == "parallel":
            result = await self._parallel(runtimes, user_query)
        elif strategy == "supervisor":
            result = await self._supervisor(runtimes, user_query)
        else:
            msg = f"Unknown strategy: {strategy}"
            raise ValueError(msg)

        # Auto-extract charts if user asked for visualization
        chart_keywords = ["图", "chart", "折线", "柱状", "饼图", "散点",
                         "可视化", "曲线", "展示", "画", "plot", "graph",
                         "面积图", "雷达图"]
        if any(kw in user_query.lower() for kw in chart_keywords):
            try:
                chart_specs = await self._extract_charts(result.content, user_query)
                result.chart_specs = chart_specs
            except Exception:
                pass

        return result

    async def _run_agent_with_tools(
        self,
        runtime: AgentRuntime,
        query: str,
    ) -> dict[str, Any]:
        """Run one agent with tool binding. Emits agent.started, tool.*, agent.finished events."""
        agent_name = runtime.name
        t0 = int(asyncio.get_event_loop().time() * 1000)

        self._emit("agent.started", agent=agent_name, display=runtime.display_name)

        # Build LLM with tools bound
        llm = runtime.llm
        lc_tools = []
        if runtime.tools:
            for t in runtime.tools:
                if hasattr(t, 'name') and hasattr(t, 'execute'):
                    from langchain_core.tools import tool
                    lc_tools.append(_build_lc_tool(t))
            if lc_tools:
                llm = llm.bind_tools(lc_tools)

        messages = [
            SystemMessage(content=runtime.system_prompt),
            HumanMessage(content=query),
        ]

        # Tool call loop (max 5 rounds)
        tool_call_history: list[dict] = []
        max_rounds = 5
        for round_idx in range(max_rounds):
            response = await llm.ainvoke(messages)

            # Check for tool calls
            tool_calls = getattr(response, 'tool_calls', None)
            if not tool_calls:
                # No more tools — final answer
                elapsed = int(asyncio.get_event_loop().time() * 1000) - t0
                self._emit("agent.finished", agent=agent_name, elapsed_ms=elapsed)
                return {
                    "agent": agent_name,
                    "status": "ok",
                    "output": str(response.content).strip(),
                    "tool_calls": tool_call_history,
                }

            # Process tool calls
            messages.append(response)
            for tc in tool_calls:
                tc_id = tc.get("id", f"tc-{round_idx}")
                tc_name = tc.get("name", "unknown")
                tc_args = tc.get("args", {})

                self._emit("tool.started", tool_call_id=tc_id, tool=tc_name,
                          agent=agent_name, arguments=tc_args)

                # Execute tool via BaseTool.execute() — pass args directly
                tool_obj = _find_tool(runtime.tools, tc_name)
                if tool_obj and hasattr(tool_obj, 'execute'):
                    try:
                        result = await tool_obj.execute(dict(tc_args))
                        result_str = str(result)
                        self._emit("tool.finished", tool_call_id=tc_id, tool=tc_name,
                                  agent=agent_name, result=result_str[:500],
                                  status="done")
                    except Exception as e:
                        result_str = f"Tool error: {e}"
                        self._emit("tool.failed", tool_call_id=tc_id, tool=tc_name,
                                  agent=agent_name, error=str(e), status="failed")
                else:
                    result_str = f"Tool '{tc_name}' not found in runtime tools."
                    self._emit("tool.failed", tool_call_id=tc_id, tool=tc_name,
                              agent=agent_name, error=f"Tool not found: {tc_name}",
                              status="failed")

                tool_call_history.append({
                    "id": tc_id, "name": tc_name,
                    "arguments": tc_args, "status": "done",
                    "result": result_str[:500],
                })
                messages.append(ToolMessage(content=result_str, tool_call_id=tc_id))

        # Max rounds reached
        elapsed = int(asyncio.get_event_loop().time() * 1000) - t0
        self._emit("agent.finished", agent=agent_name, elapsed_ms=elapsed)
        last_response = response if 'response' in dir() else None
        return {
            "agent": agent_name,
            "status": "ok",
            "output": str(last_response.content).strip() if last_response else "",
            "tool_calls": tool_call_history,
        }

    async def _sequential(
        self, runtimes: list[AgentRuntime], user_query: str,
    ) -> CollaborationResult:
        context = user_query
        agent_results: list[dict] = []

        for runtime in runtimes:
            result = await self._run_agent_with_tools(runtime, context)
            agent_results.append(result)
            if result["status"] == "error":
                break
            context = (
                f"Previous agent ({runtime.name}) result:\n{result['output']}\n\n"
                f"Original request: {user_query}"
            )

        final = agent_results[-1].get("output", "") if agent_results else ""
        return CollaborationResult(content=final, agent_results=agent_results)

    async def _parallel(
        self, runtimes: list[AgentRuntime], user_query: str,
    ) -> CollaborationResult:
        results = await asyncio.gather(
            *[self._run_agent_with_tools(r, user_query) for r in runtimes],
            return_exceptions=True,
        )
        cleaned = []
        for r in results:
            if isinstance(r, Exception):
                cleaned.append({"agent": "unknown", "status": "error", "error": str(r)})
            else:
                cleaned.append(r)

        parts = [f"[{r['agent']}]: {r['output']}" for r in cleaned if r["status"] == "ok"]
        return CollaborationResult(content="\n\n".join(parts), agent_results=cleaned)

    async def _supervisor(
        self, runtimes: list[AgentRuntime], user_query: str,
    ) -> CollaborationResult:
        if len(runtimes) < 2:
            return await self._sequential(runtimes, user_query)

        supervisor = runtimes[0]
        workers = runtimes[1:]

        decompose_prompt = f"""You are a task supervisor. Decompose this user request:
{user_query}

Available workers: {', '.join([w.name for w in workers])}

Output JSON array: [{{"worker": "worker_name", "task": "specific task"}}]"""
        try:
            resp = await supervisor.llm.ainvoke([
                SystemMessage(content=supervisor.system_prompt),
                HumanMessage(content=decompose_prompt),
            ])
            subtasks = json.loads(str(resp.content).strip())
        except Exception:
            return await self._parallel(runtimes, user_query)

        worker_map = {w.name: w for w in workers}

        async def run_worker(task_info):
            name = task_info.get("worker", "")
            task = task_info.get("task", user_query)
            w = worker_map.get(name)
            if not w:
                return {"agent": name, "status": "error", "error": "Not found"}
            return await self._run_agent_with_tools(w, task)

        worker_results = await asyncio.gather(*[run_worker(t) for t in subtasks])

        # Supervisor synthesizes
        outputs = "\n".join([f"[{r.get('agent')}]: {r.get('output', r.get('error', ''))}"
                            for r in worker_results])
        synth = f"""Original: {user_query}\n\nWorker results:\n{outputs}\n\nProvide final synthesized answer."""
        try:
            resp = await supervisor.llm.ainvoke([
                SystemMessage(content=supervisor.system_prompt),
                HumanMessage(content=synth),
            ])
            final = str(resp.content).strip()
        except Exception:
            final = outputs

        return CollaborationResult(content=final, agent_results=[
            {"agent": supervisor.name, "status": "ok"},
            *worker_results,
        ])


    async def _extract_charts(
        self, content: str, user_query: str,
    ) -> list[dict]:
        """Extract chart specs from collaboration result using lightweight LLM call."""
        from langchain_openai import ChatOpenAI
        from config import settings

        # Truncate content to first 3000 chars for chart extraction
        snippet = content[:3000]

        prompt = f"""Extract structured chart data from this analysis text.
User asked: {user_query}

Analysis result:
{snippet}

Output a JSON array of chart specs. Each chart spec has:
- "title": chart title
- "chartType": "line" | "bar" | "pie" | "scatter" | "area"
- "description": one-line summary
- "xAxisLabel": X axis label
- "yAxisLabel": Y axis label
- "data": [{{"name": "label", "value": number, "group": "optional group"}}]

Rules:
- Only create charts if the data is present in the text
- Use numbers from the analysis, not made-up values
- Max 3 charts
- If no chartable data, return empty array []
- Output ONLY the JSON array, no explanation"""

        llm = ChatOpenAI(
            model=settings.model,
            temperature=0.1,
            streaming=False,
            api_key=settings.api_key,
            base_url=settings.base_url,
        )

        try:
            resp = await llm.ainvoke([HumanMessage(content=prompt)])
            charts = json.loads(str(resp.content).strip())
            if isinstance(charts, list):
                # Ensure each chart has an id
                for i, c in enumerate(charts):
                    if isinstance(c, dict) and "id" not in c:
                        c["id"] = f"chart-{i}"
                return charts
        except Exception as e:
            logging.warning("Chart extraction failed: %s", e)

        return []


def _find_tool(tools: list, name: str):
    for t in tools:
        if hasattr(t, 'name') and getattr(t, 'name', '') == name:
            return t
    return None
