import asyncio
import logging
import uuid
import random

from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from sse_starlette.sse import EventSourceResponse

from api.schemas import GenerateRequest
from api.events.event_mapper import (
    EventMapContext,
    emit_chart_envelopes,
    emit_guard_reason_envelope,
    emit_final_summary_envelope,
    extract_last_assistant_text,
    map_langgraph_event_to_envelopes,
)
from config import settings
from core.runtime import get_checkpointer, get_pool, get_tool_registry


def _is_internal_react_message(content: str) -> bool:
    """Filter out internal ReAct system messages from history."""
    if not content:
        return False
    stripped = content.strip()
    # System action messages: [SYSTEM: You called ...]
    if stripped.startswith("[SYSTEM:") or stripped.startswith("[Tool result:"):
        return True
    # Legacy ReAct format (for old conversations)
    if stripped.startswith("Action:") and "\nAction Input:" in stripped:
        return True
    if stripped.startswith("Observation (") and "):" in stripped[:30]:
        return True
    # Tool-call JSON that leaked into messages
    if stripped.startswith('{"action"'):
        return True
    # Chart planner JSON leak
    if stripped.startswith('{"need_chart"'):
        return True
    return False
from decorator.timeit import timeit
from domain.event_envelope import (
    build_envelope,
    envelope_chart,
    envelope_error,
    envelope_message_delta,
    envelope_message_done,
    envelope_message_tool_call,
    envelope_token,
    to_sse_data,
)
from graph.graph import create_agent_graph
from graph.multi_agent_graph import create_multi_agent_graph
from core.router_agent import RouterAgent
from core.agent_factory import AgentFactory
from core.collaboration import CollaborationEngine
from core.runtime import get_checkpointer, get_tool_registry, get_agent_repository, get_pool
from observability.trace import ensure_trace_context

router = APIRouter(prefix="/api/v1", tags=["chat"])

MOCK_RESPONSES = [
    "Hello! I am AI Assistant V0.2. How can I help you today?",
    "This is a mock response. The AI service is running in mock mode without a real LLM API key.",
    "Nice to meet you! I can answer many kinds of questions even in test mode.",
    "The chat service is working. Tokens are streamed in real time.",
    "V0.2 is up and running. Streaming output is enabled and healthy.",
]


def _tool_names() -> set[str]:
    registry = get_tool_registry()
    if not registry:
        return set()
    try:
        return {str(t.get("name", "")).strip().lower() for t in registry.list_tools() if isinstance(t, dict)}
    except Exception:
        return set()


@router.post("/generate/stream")
async def stream_generate(request: GenerateRequest):
    @timeit
    async def event_generator():
        trace_ctx = ensure_trace_context(request.conversation_id)

        # Use frontend-provided messageId, or generate fallback
        message_id = request.message_id or f"msg-{uuid.uuid4().hex[:12]}"

        # Load agent if specified
        agent_id = request.agent_id
        logging.info("[CHAT] stream start: message_id=%s agent_id=%s conversation_id=%s message=%s",
                     message_id, agent_id, request.conversation_id, request.message[:80])
        if agent_id:
            agent_repo = get_agent_repository()
            agent_def = await agent_repo.get_by_id(agent_id)
            if not agent_def:
                yield to_sse_data(envelope_message_done(
                    trace_ctx, message_id, status="error",
                    error=f"Agent not found: {agent_id}",
                ))
                return
            active_agent = agent_id
        else:
            active_agent = trace_ctx.agent_id or "default"

        event_ctx = EventMapContext(trace_ctx=trace_ctx, known_tools=_tool_names())
        try:
            if not settings.api_key:
                # Simulated tool call for UI demonstration
                tc_id = uuid.uuid4().hex[:12]
                # tool call: running
                yield to_sse_data(envelope_message_tool_call(trace_ctx, message_id, {
                    "id": tc_id, "name": "search",
                    "arguments": {"query": request.message[:50]},
                    "status": "running",
                }))
                await asyncio.sleep(0.3)
                # tool call: done
                yield to_sse_data(envelope_message_tool_call(trace_ctx, message_id, {
                    "id": tc_id, "name": "search",
                    "status": "done",
                    "result": "Mock search results: found 3 relevant documents about '{}'.".format(request.message[:30]),
                }))
                await asyncio.sleep(0.2)

                response = random.choice(MOCK_RESPONSES)
                for char in response:
                    yield to_sse_data(envelope_message_delta(trace_ctx, message_id, char))
                    await asyncio.sleep(0.05)
                yield to_sse_data(envelope_message_done(trace_ctx, message_id, status="done"))
            else:
                checkpointer = get_checkpointer()

                # ── Multi-Agent Graph with Real-Time Streaming ────────────
                from core.streaming_event_bus import StreamingEventBus

                event_bus = StreamingEventBus()
                agent_repo = get_agent_repository()
                router = RouterAgent(repository=agent_repo)
                factory = AgentFactory()
                engine = CollaborationEngine(event_bus=event_bus)
                graph = create_multi_agent_graph(
                    router=router, factory=factory, engine=engine,
                    checkpointer=checkpointer, event_bus=event_bus,
                )

                logging.info("[CHAT] streaming multi-agent graph with event bus")

                inputs = {
                    "messages": [HumanMessage(content=request.message)],
                    "conversation_id": trace_ctx.conversation_id,
                    "active_agent": active_agent,
                    "chart_specs": [],
                    "blocks": [],
                    "route": "start",
                }

                thread_id = trace_ctx.conversation_id
                config: RunnableConfig = {"configurable": {"thread_id": thread_id}, "recursion_limit": 256}

                final_state = None
                assistant_text_emitted = False
                charts_sent: set = set()

                # Emit conversation.started
                yield to_sse_data(build_envelope(
                    "conversation.started", trace_ctx,
                    payload={"messageId": message_id, "agentId": active_agent},
                ))

                # Run graph stream + event bus reader concurrently via asyncio.Queue
                merge_queue: asyncio.Queue = asyncio.Queue()

                async def graph_runner():
                    try:
                        async for event in graph.astream_events(inputs, config=config, version="v2"):
                            mapped, _, captured = map_langgraph_event_to_envelopes(
                                event, event_ctx, None, message_id=message_id,
                            )
                            if captured is not None:
                                nonlocal final_state
                                final_state = captured
                            for envelope in mapped:
                                if envelope.get("type") == "message.delta":
                                    nonlocal assistant_text_emitted
                                    assistant_text_emitted = True
                                await merge_queue.put(("graph", envelope))
                    except Exception as e:
                        await merge_queue.put(("error", str(e)))
                    finally:
                        await merge_queue.put(("graph_done", None))

                async def bus_runner():
                    try:
                        async for bus_event in event_bus.events():
                            envelope = {
                                "type": bus_event.type,
                                "schemaVersion": "1.0",
                                "conversationId": trace_ctx.conversation_id,
                                "messageId": message_id,
                                "agentId": active_agent,
                                "timestamp": bus_event.timestamp,
                                "payload": bus_event.data,
                            }
                            await merge_queue.put(("bus", envelope))
                    except Exception:
                        pass
                    finally:
                        await merge_queue.put(("bus_done", None))

                graph_task = asyncio.create_task(graph_runner())
                bus_task = asyncio.create_task(bus_runner())

                graph_done_flag = False
                bus_done_flag = False

                while not (graph_done_flag and bus_done_flag):
                    source, data = await merge_queue.get()

                    if source == "graph_done":
                        graph_done_flag = True
                    elif source == "bus_done":
                        bus_done_flag = True
                    elif source == "error":
                        yield to_sse_data(envelope_error(trace_ctx, str(data)))
                        graph_done_flag = True
                    else:
                        # Bus events (progress) get priority — yield immediately
                        yield to_sse_data(data)

                # Cleanup
                await asyncio.gather(graph_task, bus_task, return_exceptions=True)
                event_bus.close()

                # Emit chart specs from chart_planner_node output
                if final_state:
                    chart_specs = final_state.get("chart_specs")
                    if isinstance(chart_specs, list):
                        for cs in chart_specs:
                            if isinstance(cs, dict) and cs:
                                yield to_sse_data(envelope_chart(trace_ctx, cs))

                # Stream complete
                yield to_sse_data(envelope_message_done(trace_ctx, message_id, status="done"))

                # Async persist message to database
                try:
                    pool = get_pool()
                    if pool and final_state:
                        from db.chat_message_repository import save_message
                        message_dict = {
                            "id": message_id,
                            "conversation_id": trace_ctx.conversation_id,
                            "role": "assistant",
                            "content": extract_last_assistant_text(final_state),
                            "toolCalls": final_state.get("tool_steps", []),
                            "status": "done",
                            "agentId": trace_ctx.agent_id,
                        }
                        asyncio.create_task(save_message(pool, message_dict))
                except (ImportError, Exception):
                    pass

        except Exception as e:
            yield to_sse_data(envelope_error(trace_ctx, str(e)))

    return EventSourceResponse(event_generator())


@timeit
@router.get("/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    # Try new DB table first
    pool = get_pool()
    if pool:
        from db.chat_message_repository import get_messages_by_conversation
        messages = await get_messages_by_conversation(pool, conversation_id)
        if messages:
            return {"messages": messages}

    # Fallback: old checkpoint-based history
    checkpointer = get_checkpointer()
    if not checkpointer:
        return {"messages": []}

    config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}
    state_history = await checkpointer.aget_tuple(config)

    if not state_history or "messages" not in state_history.checkpoint["channel_values"]:
        return {"messages": []}

    channel_values = state_history.checkpoint["channel_values"]
    raw_messages = channel_values["messages"]
    formatted_messages = []
    for msg in raw_messages:
        role = "user" if msg.type == "human" else "assistant"
        content = msg.content if isinstance(msg.content, str) else str(msg.content)

        # Filter out internal ReAct messages that should not appear in user-facing history
        if _is_internal_react_message(content):
            continue

        formatted_messages.append({"role": role, "content": content})

    # Extract chart_specs and tool_steps from checkpoint state for frontend rendering
    result = {"messages": formatted_messages}

    chart_specs = channel_values.get("chart_specs")
    if isinstance(chart_specs, list) and chart_specs:
        result["chartDatas"] = chart_specs
    # Legacy fallback
    elif channel_values.get("chart_spec"):
        cs = channel_values.get("chart_spec")
        if isinstance(cs, dict) and cs:
            result["chartDatas"] = [cs]

    tool_steps = channel_values.get("tool_steps")
    if isinstance(tool_steps, list) and tool_steps:
        result["toolSteps"] = tool_steps

    return result
