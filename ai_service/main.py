from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import asyncio
import random
import json
from config import settings

app = FastAPI(title="AI Chat Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOCK_RESPONSES = [
    "你好！我是 AI 助手 V0.1 版本。我可以和你进行基础对话，有什么我可以帮助你的吗？",
    "这是一个测试响应。当前 AI 服务运行在 Mock 模式下，不需要真实的 LLM API Key。",
    "很高兴见到你！我可以回答各种问题，虽然现在是测试模式，但我已经准备好与你对话了。",
    "今天天气不错呢！虽然我只是个测试版本的 AI，但我很乐意陪你聊天。",
    "V0.1 版本的 AI 对话系统已经成功启动！流式传输功能工作正常，你看到的每个字都是实时输出的。",
]


class GenerateRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    stream: bool = True


@app.post("/api/v1/generate/stream")
async def stream_generate(request: GenerateRequest):
    async def event_generator():
        try:
            api_key = settings.get_api_key()
            
            if not api_key:
            # Mock 模式
                response = random.choice(MOCK_RESPONSES)
                for char in response:
                    yield {
                        "data": json.dumps({"token": char, "conversation_id": request.conversation_id})
                    }
                    await asyncio.sleep(0.05)
            else:
                # 真实 LLM 模式
                from langchain_openai import ChatOpenAI
                
                llm = ChatOpenAI(
                    model=settings.get_model(),
                    temperature=settings.temperature,
                    streaming=True,
                    api_key=api_key,
                    base_url=settings.get_base_url(),
                )
                
                messages = [("user", request.message)]
                
                async for chunk in llm.astream(messages):
                    if chunk.content:
                        yield {
                            "data": json.dumps({
                                "token": chunk.content,
                                "conversation_id": request.conversation_id
                            })
                        }
                
        except Exception as e:
            yield {"data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@app.get("/health")
async def health_check():
    api_key = settings.get_api_key()
    mode = "llm" if api_key else "mock"
    return {
        "status": "healthy",
        "mode": mode,
        "model": settings.get_model() if api_key else None
    }


@app.get("/")
async def root():
    return {"message": "AI Chat Mock Service V0.1", "endpoints": ["/health", "/api/v1/generate/stream"]}
