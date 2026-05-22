import asyncio
import json
import random

from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from sse_starlette.sse import EventSourceResponse

from api.schemas import GenerateRequest
from config import settings
from core.runtime import get_checkpointer
from decorator.timeit import timeit
from graph.graph import create_agent_graph

router = APIRouter(prefix="/api/v1", tags=["chat"])

MOCK_RESPONSES = [
    "Hello! I am AI Assistant V0.2. How can I help you today?",
    "This is a mock response. The AI service is running in mock mode without a real LLM API key.",
    "Nice to meet you! I can answer many kinds of questions even in test mode.",
    "The chat service is working. Tokens are streamed in real time.",
    "V0.2 is up and running. Streaming output is enabled and healthy.",
]


def _safe_json_loads(raw: str) -> dict | None:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _is_tool_action_json(raw: str) -> bool:
    parsed = _safe_json_loads(raw.strip())
    if not parsed:
        return False
    action = str(parsed.get("action", "")).strip()
    return bool(action)


def _summarize_tool_result(tool_name: str, output: dict) -> str:
    tool_result_raw = output.get("tool_result")
    if isinstance(tool_result_raw, str):
        parsed = _safe_json_loads(tool_result_raw)
    elif isinstance(tool_result_raw, dict):
        parsed = tool_result_raw
    else:
        parsed = None

    if not parsed:
        return f"工具 `{tool_name}` 执行完成。"

    if not parsed.get("ok", False):
        err = parsed.get("error")
        return f"工具 `{tool_name}` 执行失败：{err}"

    data = parsed.get("data") or {}
    query = data.get("query") if isinstance(data, dict) else None
    results = data.get("results") if isinstance(data, dict) else None
    if isinstance(results, list):
        return f"工具 `{tool_name}` 执行完成，命中 {len(results)} 条结果（query: {query or '-'}）。"

    return f"工具 `{tool_name}` 执行成功。"


def _extract_last_assistant_text(final_state: dict | None) -> str:
    """Extract the last assistant message text from graph final state."""
    if not isinstance(final_state, dict):
        return ""

    raw_messages = final_state.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        return ""

    for msg in reversed(raw_messages):
        # LangChain message objects
        msg_type = getattr(msg, "type", None)
        msg_content = getattr(msg, "content", None)
        if msg_type == "ai" and isinstance(msg_content, str) and msg_content.strip():
            return msg_content

        # Dict-like fallback (history / serialization path)
        if isinstance(msg, dict):
            role = msg.get("role") or msg.get("type")
            content = msg.get("content")
            if role in {"assistant", "ai"} and isinstance(content, str) and content.strip():
                return content

    return ""


@router.post("/generate/stream")
async def stream_generate(request: GenerateRequest):
    @timeit
    async def event_generator():
        try:
            if not settings.api_key:
                response = random.choice(MOCK_RESPONSES)
                for char in response:
                    yield {
                        "data": json.dumps(
                            {
                                "type": "token",
                                "token": char,
                                "content": char,
                                "conversationId": request.conversation_id,
                            }
                        )
                    }
                    await asyncio.sleep(0.05)
            else:
                checkpointer = get_checkpointer()
                graph = create_agent_graph(checkpointer=checkpointer)
                inputs = {
                    "messages": [HumanMessage(content=request.message)],
                    "tool_steps": [],
                    "iteration_count": 0,
                    "current_tool": None,
                    "tool_input": None,
                    "tool_result": None,
                    "last_tool_name": None,
                    "last_tool_query": None,
                }

                thread_id = request.conversation_id if request.conversation_id else "default-thread"
                config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

                # 用于判断工具摘要是否已发送
                tool_summary_sent = False
                final_state = None
                collecting_control_json = False
                control_json_buffer = ""
                assistant_text_emitted = False

                async for event in graph.astream_events(inputs, config=config, version="v2"):
                    event_type = event.get("event")
                    event_name = event.get("name")

                    # 1) 流式 token 事件
                    if event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        content = getattr(chunk, "content", "")
                        if content:
                            # 过滤模型工具规划 JSON，避免前端闪出 {"action":...}
                            if collecting_control_json:
                                control_json_buffer += content
                                if "}" not in control_json_buffer:
                                    continue

                                if _is_tool_action_json(control_json_buffer):
                                    collecting_control_json = False
                                    control_json_buffer = ""
                                    continue

                                # 不是工具规划 JSON，则按普通文本回放
                                content = control_json_buffer
                                collecting_control_json = False
                                control_json_buffer = ""
                            elif content.lstrip().startswith("{"):
                                collecting_control_json = True
                                control_json_buffer = content
                                if "}" not in control_json_buffer:
                                    continue

                                if _is_tool_action_json(control_json_buffer):
                                    collecting_control_json = False
                                    control_json_buffer = ""
                                    continue

                                content = control_json_buffer
                                collecting_control_json = False
                                control_json_buffer = ""

                            yield {
                                "data": json.dumps(
                                    {
                                        "type": "token",
                                        "token": content,
                                        "content": content,
                                        "conversationId": request.conversation_id,
                                    }
                                )
                            }
                            assistant_text_emitted = True

                    # 2) 工具开始事件（仅真实 tool 节点）
                    elif event_type == "on_chain_start" and event_name == "tool":
                        input_state = event.get("data", {}).get("input", {})
                        tool_name = "unknown"
                        if isinstance(input_state, dict):
                            tool_name = input_state.get("current_tool") or tool_name

                        yield {
                            "data": json.dumps(
                                {
                                    "type": "tool_start",
                                    "toolName": tool_name,
                                    "content": f"\n\n🛠️ 正在调用工具：{tool_name}...\n",
                                    "conversationId": request.conversation_id,
                                }
                            )
                        }

                    # 3) 工具完成事件（仅真实 tool 节点）
                    elif event_type == "on_chain_end" and event_name == "tool":
                        output_state = event.get("data", {}).get("output", {})
                        input_state = event.get("data", {}).get("input", {})
                        tool_name = "tool"
                        if isinstance(output_state, dict):
                            tool_name = output_state.get("current_tool") or tool_name
                        if tool_name == "tool" and isinstance(input_state, dict):
                            tool_name = input_state.get("current_tool") or tool_name

                        summary = _summarize_tool_result(tool_name, output_state if isinstance(output_state, dict) else {})
                        yield {
                            "data": json.dumps(
                                {
                                    "type": "tool_result",
                                    "toolName": tool_name,
                                    "content": f"{summary}\n\n",
                                    "conversationId": request.conversation_id,
                                }
                            )
                        }

                    # 4) 图执行过程中的最终状态捕获（不只依赖 name==agent）
                    elif event_type == "on_chain_end":
                        output_state = event.get("data", {}).get("output", {})
                        if isinstance(output_state, dict) and "messages" in output_state:
                            final_state = output_state

                if collecting_control_json and control_json_buffer and not _is_tool_action_json(control_json_buffer):
                    yield {
                        "data": json.dumps(
                            {
                                "type": "token",
                                "token": control_json_buffer,
                                "content": control_json_buffer,
                                "conversationId": request.conversation_id,
                            }
                        )
                    }
                    assistant_text_emitted = True

                # 无 token 流时（例如 fallback AIMessage），兜底发一次最终文本
                if not assistant_text_emitted:
                    fallback_text = _extract_last_assistant_text(final_state)
                    if fallback_text:
                        yield {
                            "data": json.dumps(
                                {
                                    "type": "token",
                                    "token": fallback_text,
                                    "content": fallback_text,
                                    "conversationId": request.conversation_id,
                                }
                            )
                        }

                # 5) 在所有 token 流完成后，发送统一的工具摘要事件
                if final_state and not tool_summary_sent:
                    tool_steps = final_state.get("tool_steps", [])
                    if tool_steps:
                        yield {
                            "data": json.dumps(
                                {
                                    "type": "tool_summary",
                                    "steps": tool_steps,
                                    "conversationId": request.conversation_id,
                                }
                            )
                        }
                        tool_summary_sent = True

        except Exception as e:
            yield {"data": json.dumps({"type": "error", "error": str(e)})}

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

    raw_messages = state_history.checkpoint["channel_values"]["messages"]
    formatted_messages = []
    for msg in raw_messages:
        role = "user" if msg.type == "human" else "assistant"
        formatted_messages.append({"role": role, "content": msg.content})

    return {"messages": formatted_messages}
