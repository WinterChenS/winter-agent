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
                 images: dict[str, str] | None = None) -> None:
        self.content = content
        self.agent_results = agent_results
        self.images = images or {}


def _build_lc_tool(tool_obj):
    """Build a LangChain StructuredTool from a BaseTool, using its input_schema."""
    from langchain_core.tools import StructuredTool

    name = tool_obj.name
    desc = getattr(tool_obj, 'description', name) or name
    input_schema = getattr(tool_obj, 'input_schema', None)

    # Validate input_schema — must be a dict
    if not isinstance(input_schema, dict) or not input_schema.get('properties'):
        logger.warning("Tool %s has invalid input_schema, skipping", name)
        return None

    async def _execute(**kwargs) -> str:
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
                    lc = _build_lc_tool(t)
                    if lc:
                        lc_tools.append(lc)
            if lc_tools:
                llm = llm.bind_tools(lc_tools)

        messages = [
            SystemMessage(content=runtime.system_prompt),
            HumanMessage(content=query),
        ]

        # Tool call loop (max 5 rounds)
        tool_call_history: list[dict] = []
        max_rounds = 5
        try:
            for round_idx in range(max_rounds):
                response = await llm.ainvoke(messages)

            # Check for tool calls
            tool_calls = getattr(response, 'tool_calls', None)
            if not tool_calls:
                # No more tools — final answer
                elapsed = int(asyncio.get_event_loop().time() * 1000) - t0
                self._emit("agent.finished", agent=agent_name, elapsed_ms=elapsed)
                # Scan for generated images and upload to MinIO
                final_output = str(response.content).strip()
                images = self._scan_and_upload_images(final_output)
                for filename, url in images.items():
                    self._emit("image.uploaded", filename=filename, url=url)
                    final_output = final_output.replace(filename, url)
                    import re
                    final_output = re.sub(
                        rf'https?://[^\s)]*{re.escape(filename)}', url,
                        final_output
                    )
                return {
                    "agent": agent_name,
                    "status": "ok",
                    "output": final_output,
                    "tool_calls": tool_call_history,
                    "images": images,
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
        except Exception as e:
            elapsed = int(asyncio.get_event_loop().time() * 1000) - t0
            self._emit("agent.finished", agent=agent_name, elapsed_ms=elapsed)
            return {
                "agent": agent_name,
                "status": "error",
                "output": "",
                "error": str(e),
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
        all_images = {}
        for r in agent_results:
            if isinstance(r.get("images"), dict):
                all_images.update(r["images"])
        return CollaborationResult(content=final, agent_results=agent_results, images=all_images)

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


    def _scan_and_upload_images(self, output_text: str) -> dict[str, str]:
        """Scan tool output for generated images and upload to MinIO."""
        try:
            from services.minio_client import scan_and_upload_images
            return scan_and_upload_images(output_text)
        except Exception:
            return {}

def _find_tool(tools: list, name: str):
    for t in tools:
        if hasattr(t, 'name') and getattr(t, 'name', '') == name:
            return t
    return None
