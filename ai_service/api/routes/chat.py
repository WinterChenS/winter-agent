import asyncio
import random

from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from sse_starlette.sse import EventSourceResponse

from api.schemas import GenerateRequest
from api.events.event_mapper import (
    EventMapContext,
    emit_chart_envelope,
    emit_guard_reason_envelope,
    emit_final_summary_envelope,
    extract_last_assistant_text,
    is_tool_action_json,
    map_langgraph_event_to_envelopes,
    process_stream_token_event,
)
from config import settings
from core.runtime import get_checkpointer, get_tool_registry


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
    envelope_error,
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
        event_ctx = EventMapContext(trace_ctx=trace_ctx, known_tools=_tool_names())
        try:
            if not settings.api_key:
                response = random.choice(MOCK_RESPONSES)
                for char in response:
                    yield to_sse_data(envelope_token(trace_ctx, char))
                    await asyncio.sleep(0.05)
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
                    "active_agent": trace_ctx.agent_id,
                    "chart_intent": None,
                    "chart_spec": None,
                }

                thread_id = trace_ctx.conversation_id
                config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

                # 用于判断工具摘要是否已发送
                tool_summary_sent = False
                final_state = None
                collecting_control_json = False
                control_json_buffer = ""
                assistant_text_emitted = False
                saw_tool_event = False
                assistant_text_emitted_after_tool = False
                active_tool_span_id: str | None = None

                async for event in graph.astream_events(inputs, config=config, version="v2"):
                    event, collecting_control_json, control_json_buffer = process_stream_token_event(
                        event,
                        collecting_control_json,
                        control_json_buffer,
                        event_ctx.known_tools,
                    )
                    if event is None:
                        continue

                    mapped, active_tool_span_id, captured_final_state = map_langgraph_event_to_envelopes(
                        event,
                        event_ctx,
                        active_tool_span_id,
                    )
                    if captured_final_state is not None:
                        final_state = captured_final_state

                    for envelope in mapped:
                        envelope_type = envelope.get("type")
                        if envelope_type in {"tool_start", "tool_result"}:
                            saw_tool_event = True
                            assistant_text_emitted_after_tool = False
                        if envelope_type == "token":
                            assistant_text_emitted = True
                            if saw_tool_event:
                                assistant_text_emitted_after_tool = True
                        yield to_sse_data(envelope)

                if collecting_control_json and control_json_buffer and not is_tool_action_json(
                    control_json_buffer,
                    event_ctx.known_tools,
                ):
                    yield to_sse_data(envelope_token(trace_ctx, control_json_buffer))
                    assistant_text_emitted = True

                # 如果仅出现了工具过程 token（如“我先搜索一下”）但工具后没有最终回答 token，
                # 兜底补发 final_state 中的最后一条 assistant 文本，避免前端只看到工具步骤。
                if (not assistant_text_emitted) or (saw_tool_event and not assistant_text_emitted_after_tool):
                    fallback_text = extract_last_assistant_text(final_state)
                    if fallback_text:
                        yield to_sse_data(envelope_token(trace_ctx, fallback_text))

                # 5) 在所有 token 流完成后，发送统一的工具摘要事件
                guard_envelope = emit_guard_reason_envelope(final_state, event_ctx)
                if guard_envelope:
                    yield to_sse_data(guard_envelope)

                if final_state and not tool_summary_sent:
                    summary_envelope = emit_final_summary_envelope(final_state, event_ctx)
                    if summary_envelope:
                        yield to_sse_data(summary_envelope)
                        tool_summary_sent = True

                # 6) 发送图表事件（如果 chart_node 生成了 ChartSpec）
                if final_state:
                    chart_envelope = emit_chart_envelope(final_state, event_ctx)
                    if chart_envelope:
                        yield to_sse_data(chart_envelope)

        except Exception as e:
            yield to_sse_data(envelope_error(trace_ctx, str(e)))

    return EventSourceResponse(event_generator())


@timeit
@router.get("/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
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

    # Extract chart_spec and tool_steps from checkpoint state for frontend rendering
    result = {"messages": formatted_messages}

    chart_spec = channel_values.get("chart_spec")
    if isinstance(chart_spec, dict) and chart_spec:
        result["chartData"] = chart_spec

    tool_steps = channel_values.get("tool_steps")
    if isinstance(tool_steps, list) and tool_steps:
        result["toolSteps"] = tool_steps

    return result
