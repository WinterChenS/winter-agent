from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from api.routes.chat import router as chat_router
from api.routes.system import router as system_router
from config import settings
from core.runtime import set_runtime, set_tool_registry
from tools import ToolRegistry
from tools.echo import EchoTool
from tools.search import SearchTool


# FastApi 生命周期的钩子，使用@asynccontextmanager注解
@asynccontextmanager
async def lifespan(app: FastAPI):
    pg_pool: AsyncConnectionPool | None = None
    checkpointer: AsyncPostgresSaver | None = None

    if settings.api_key:
        print("Initializing PostgreSQL pool for LangGraph...")
        pg_pool = AsyncConnectionPool(
            conninfo=settings.postgres_uri,
            max_size=10,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
            },
        )
        checkpointer = AsyncPostgresSaver(pg_pool)
        await checkpointer.setup()
        print("PostgreSQL checkpointer is ready.")

    set_runtime(pg_pool, checkpointer)

    if pg_pool:
        await pg_pool.close()
    set_runtime(None, None)

    tool_registry = ToolRegistry()
    tool_registry.register(SearchTool())
    tool_registry.register(EchoTool())
    set_tool_registry(tool_registry)
    yield


# 初始化 FastAPI 应用程序实例，这里挂载 lifespan 用于启动和关闭时的生命周期钩子
app = FastAPI(title="AI Chat Service", version="0.2.0", lifespan=lifespan)

# 配置 CORS（跨域资源共享）中间件，允许前端网页连通并访问此后端 API 接口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # 允许所有域名的请求接入
    allow_credentials=True,        # 允许携带认证数据(如Cookie)
    allow_methods=["*"],           # 允许所有的 HTTP 方法 (GET, POST等)
    allow_headers=["*"],           # 允许所有的 HTTP 请求头字段
)

# 包含系统与聊天相关的路由
app.include_router(system_router)
app.include_router(chat_router)
