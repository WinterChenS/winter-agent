from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from api.routes.agents import router as agents_router
from api.routes.chat import router as chat_router
from api.routes.system import router as system_router
from config import settings
from core.runtime import set_runtime, set_tool_registry, set_agent_repository
from repositories.agent_repository import PostgresAgentRepository
from tools import ToolRegistry

# Auto-discovery: import tool modules so @tool classes register via BaseTool.__subclasses__()
import tools.browser.tool as _
import tools.sandbox.tool as _
import tools.search.tool as _
import tools.time.tool as _


# FastApi 生命周期的钩子，使用@asynccontextmanager注解
@asynccontextmanager
async def lifespan(app: FastAPI):
    pg_pool: AsyncConnectionPool | None = None
    checkpointer: AsyncPostgresSaver | None = None

    # ── 启动时初始化 ──────────────────────────────────────────────────────────
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

    # 初始化 ToolRegistry（全局单例，整个应用生命周期共用）
    tool_registry = ToolRegistry()
    tool_registry.discover()
    print(f"ToolRegistry ready: {[t['name'] for t in tool_registry.list_tools()]}")

    set_runtime(pg_pool, checkpointer)
    set_tool_registry(tool_registry)
    set_agent_repository(PostgresAgentRepository(pg_pool))

    yield  # ← 应用正常运行中

    # ── 关闭时清理 ────────────────────────────────────────────────────────────
    if pg_pool:
        await pg_pool.close()
    set_runtime(None, None)
    set_tool_registry(None)



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

# 包含系统、聊天与代理管理的路由
app.include_router(system_router)
app.include_router(chat_router)
app.include_router(agents_router)
