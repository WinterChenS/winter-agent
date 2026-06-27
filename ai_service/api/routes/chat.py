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
    envelope_chart,
    envelope_error,
    envelope_message_delta,
    envelope_message_done,
    envelope_message_tool_call,
    envelope_token,
    to_sse_data,
)
from graph.graph import create_agent_graph
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
            from core.runtime import get_agent_repository
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
                graph = create_agent_graph(checkpointer=checkpointer)
                inputs = {
                    "messages": [HumanMessage(content=request.message)],
                    "conversation_id": trace_ctx.conversation_id,
                    "tool_steps": [],
                    "iteration_count": 0,
                    "current_tool": None,
                    "tool_input": None,
                    "tool_result": None,
                    "last_tool_name": None,
                    "last_tool_query": None,
                    "consecutive_search_count": 0,
                    "last_guard_reason": None,
                    "trace_id": trace_ctx.trace_id,
                    "turn_id": trace_ctx.turn_id,
                    "span_id": trace_ctx.span_id,
                    "parent_span_id": trace_ctx.parent_span_id,
                    "active_agent": active_agent,
                    "chart_specs": [],
                    "blocks": [],
                    "route": "tool",
                }

                thread_id = trace_ctx.conversation_id
                config: RunnableConfig = {"configurable": {"thread_id": thread_id}, "recursion_limit": 256}

                tool_summary_sent = False
                final_state = None
                saw_tool_event = False
                assistant_text_emitted = False
                active_tool_span_id: str | None = None
                charts_sent: set = set()  # Track chart IDs already sent to avoid duplicates

                async for event in graph.astream_events(inputs, config=config, version="v2"):
                    mapped, active_tool_span_id, captured_final_state = map_langgraph_event_to_envelopes(
                        event, event_ctx, active_tool_span_id,
                        message_id=message_id,
                    )
                    if captured_final_state is not None:
                        final_state = captured_final_state

                    for envelope in mapped:
                        envelope_type = envelope.get("type")
                        if envelope_type in {"tool_start", "tool_result"}:
                            saw_tool_event = True
                        if envelope_type == "message.delta":
                            assistant_text_emitted = True
                        yield to_sse_data(envelope)

                    # Inline: send charts from chart_planner_node output
                    if final_state:
                        chart_specs = final_state.get("chart_specs")
                        if isinstance(chart_specs, list):
                            for cs in chart_specs:
                                if isinstance(cs, dict):
                                    cid = str(cs.get("id", ""))
                                    if cid and cid not in charts_sent:
                                        charts_sent.add(cid)
                                        yield to_sse_data(envelope_chart(trace_ctx, cs))

                # Fallback: extract answer text if no tokens emitted
                if not assistant_text_emitted:
                    fallback_text = extract_last_assistant_text(final_state)
                    if fallback_text:
                        yield to_sse_data(envelope_message_delta(trace_ctx, message_id, fallback_text))

                # Emit guard reason
                guard_envelope = emit_guard_reason_envelope(final_state, event_ctx)
                if guard_envelope:
                    yield to_sse_data(guard_envelope)

                # Emit tool summary
                if final_state and not tool_summary_sent:
                    summary_envelope = emit_final_summary_envelope(final_state, event_ctx)
                    if summary_envelope:
                        yield to_sse_data(summary_envelope)
                        tool_summary_sent = True

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
