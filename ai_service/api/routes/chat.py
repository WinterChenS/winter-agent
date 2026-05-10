import asyncio
import json
import random

from fastapi import APIRouter
from langchain_core.messages import HumanMessage
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


@router.post("/generate/stream")
async def stream_generate(request: GenerateRequest):
    @timeit
    async def event_generator():
        try:
            if not settings.api_key:
                response = random.choice(MOCK_RESPONSES)
                for char in response:
                    yield {"data": json.dumps({"token": char, "conversationId": request.conversation_id})}
                    await asyncio.sleep(0.05)
            else:
                checkpointer = get_checkpointer()
                graph = create_agent_graph(checkpointer=checkpointer)
                inputs = {"messages": [HumanMessage(content=request.message)]}

                thread_id = request.conversation_id if request.conversation_id else "default-thread"
                config = {"configurable": {"thread_id": thread_id}}

                async for event in graph.astream_events(inputs, config=config, version="v2"):
                    if event["event"] == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        if chunk.content:
                            yield {
                                "data": json.dumps(
                                    {
                                        "token": chunk.content,
                                        "conversationId": request.conversation_id,
                                    }
                                )
                            }
        except Exception as e:
            yield {"data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@timeit
@router.get("/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    checkpointer = get_checkpointer()
    if not checkpointer:
        return {"messages": []}

    config = {"configurable": {"thread_id": conversation_id}}
    state_history = await checkpointer.aget_tuple(config)

    if not state_history or "messages" not in state_history.checkpoint["channel_values"]:
        return {"messages": []}

    raw_messages = state_history.checkpoint["channel_values"]["messages"]
    formatted_messages = []
    for msg in raw_messages:
        role = "user" if msg.type == "human" else "assistant"
        formatted_messages.append({"role": role, "content": msg.content})

    return {"messages": formatted_messages}
