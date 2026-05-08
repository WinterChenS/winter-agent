from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import asyncio
import random
import json
from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from config import settings

# 声明供全局使用的连接池和 LangGraph Postgres 拦截器资源
pg_pool: AsyncConnectionPool = None
checkpointer: AsyncPostgresSaver = None

# FastApi 生命周期的钩子，使用@asynccontextmanager注解
@asynccontextmanager
async def lifespan(app: FastAPI):
    global pg_pool, checkpointer
    if settings.api_key:
        print(f"🔌 正在初始化 PostgreSQL 的 LangGraph 连接池...")
        pg_pool = AsyncConnectionPool(
            conninfo=settings.postgres_uri,
            max_size=10,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0
            }
        )
        checkpointer = AsyncPostgresSaver(pg_pool)
        # 会自动在数据库里建必要的 checkpoints 和 writes 表格
        await checkpointer.setup()
        print(f"✅ PostgreSQL LangGraph 状态机库初始化已完成。")
    yield
    if pg_pool:
        await pg_pool.close()

# 初始化 FastAPI 应用程序实例，这里挂载 lifespan 用于启动和关闭时的生命周期钩子
app = FastAPI(title="AI Chat Service", version="0.1.0", lifespan=lifespan)

# 配置 CORS（跨域资源共享）中间件，允许前端网页连通并访问此后端 API 接口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # 允许所有域名的请求接入
    allow_credentials=True,        # 允许携带认证数据(如Cookie)
    allow_methods=["*"],           # 允许所有的 HTTP 方法 (GET, POST等)
    allow_headers=["*"],           # 允许所有的 HTTP 请求头字段
)

# =============== 以下是未配置 API_KEY 情况下的 Mock(模拟) 占位回复数据 ===============
MOCK_RESPONSES = [
    "你好！我是 AI 助手 V0.1 版本。我可以和你进行基础对话，有什么我可以帮助你的吗？",
    "这是一个测试响应。当前 AI 服务运行在 Mock 模式下，不需要真实的 LLM API Key。",
    "很高兴见到你！我可以回答各种问题，虽然现在是测试模式，但我已经准备好与你对话了。",
    "今天天气不错呢！虽然我只是个测试版本的 AI，但我很乐意陪你聊天。",
    "V0.1 版本的 AI 对话系统已经成功启动！流式传输功能工作正常，你看到的每个字都是实时输出的。",
]

# 定义前端请求所发送的数据结构格式规范 (Pydantic Base Model)
class GenerateRequest(BaseModel):
    message: str                           # 用户的输入消息内容
    conversation_id: str | None = None     # 会话ID，多轮对话历史追踪用
    stream: bool = True                    # 标记是否需要流式输出打字效果��默认为 True


# 注册流式文本生成的路由接口，对应前端的 Fetch 调用
@app.post("/api/v1/generate/stream")
async def stream_generate(request: GenerateRequest):
    # 定义实际产生服务器推送事件 (SSE数据流) 的异步生成器函数
    async def event_generator():
        try:
            # 去拿我们在 .env 里写的配置好的 API 密钥
            api_key = settings.api_key

            # 如果没有配置 API 密钥，就进入 Mock(模拟测试) 模式下，方便你在没有网或没有充值时调试页面样式
            if not api_key:
                response = random.choice(MOCK_RESPONSES)
                for char in response:
                    # yield 也就是不一次性返回，而是一点点“吐”出数据
                    yield {
                        "data": json.dumps({"token": char, "conversationId": request.conversation_id})
                    }
                    # 休眠 0.05 秒，假装是大模型正在卡在思考时间中打字
                    await asyncio.sleep(0.05)
            # ---------------- 如果获取到了 API_KEY，就走下边这套真实的 LangGraph 调用链 ----------------
            else:
                from graph.graph import create_agent_graph
                from langchain_core.messages import HumanMessage

                # 创建并编译智能体的运行流转图，挂载全局数据库对象
                graph = create_agent_graph(checkpointer=checkpointer)
                # 将用户传来的明文问题(request.message)包装成 LangChain 特有的 HumanMessage(用户消息组件)
                inputs = {"messages": [HumanMessage(content=request.message)]}

                # 引入刚刚在 graph.py 加配了 Memory 的执行图，提供当前唯一的 Thread ID 作为隔离不同用户对话的凭证
                thread_id = request.conversation_id if request.conversation_id else "default-thread"
                config = {"configurable": {"thread_id": thread_id}}

                # astream_events 会去执行整个图的流程并且能在关键步骤往外抛出信息
                # 参数 version="v2" 是 LangChain 官方目前推荐的规范事件流版本
                async for event in graph.astream_events(inputs, config=config, version="v2"):
                    kind = event["event"]
                    # 我们只需要拦截 "大模型正在输出流式的具体字块" 这个事件种类（on_chat_model_stream）
                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        if chunk.content:
                            # 按照前端标准 SSE 流所要求的格式封成 json 放进 yield 吐回给前端
                            yield {
                                "data": json.dumps({
                                    "token": chunk.content,
                                    "conversationId": request.conversation_id
                                })
                            }

        except Exception as e:
            # 如果图执行内部遇到了报错(比如网络断了)，就在流的最结尾吐出一个报错消息给前端看
            yield {"data": json.dumps({"error": str(e)})}

    # 通过 FastAPI 的 EventSourceResponse 将上面写的这个数据生成器包裹成 SSE(Event-Stream) 流长链接下发
    return EventSourceResponse(event_generator())


# 健康检查接口：常用于 Docker/K8s 等部署工具检查你的容器现在死没死，正处于什么工作状态
@app.get("/health")
async def health_check():
    api_key = settings.api_key
    mode = "llm" if api_key else "mock"
    return {
        "status": "healthy",
        "mode": mode,
        "model": settings.model if api_key else None
    }


# 根目录接口：随便用浏览器一请求： http://localhost:8000 就能看到的简短标识
@app.get("/")
async def root():
    return {"message": "AI Chat Mock Service V0.1", "endpoints": ["/health", "/api/v1/generate/stream"]}

# 获取某个会话的历史记录接口，专供 Spring Boot 获取后透传给前端显示历史
@app.get("/api/v1/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    if not checkpointer:
        return {"messages": []}

    config = {"configurable": {"thread_id": conversation_id}}
    # 通过 checkpointer 拿到对应 thread_id 的所有游标状态
    state_history = await checkpointer.aget_tuple(config)

    if not state_history or "messages" not in state_history.checkpoint["channel_values"]:
        return {"messages": []}

    raw_messages = state_history.checkpoint["channel_values"]["messages"]
    formatted_messages = []

    # 遍历解析 langchain 格式为普通 json 格式
    for msg in raw_messages:
        role = "user" if msg.type == "human" else "assistant"
        formatted_messages.append({"role": role, "content": msg.content})

    return {"messages": formatted_messages}
