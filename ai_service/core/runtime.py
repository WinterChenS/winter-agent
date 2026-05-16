from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from tools import ToolRegistry

# 运行时全局资源：由 main.py 的 lifespan 初始化，在各路由中按需读取
_pg_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None
_tool_registry: ToolRegistry | None = None


def set_runtime(pool: Optional[AsyncConnectionPool], checkpointer: Optional[AsyncPostgresSaver]) -> None:
    global _pg_pool, _checkpointer
    _pg_pool = pool
    _checkpointer = checkpointer


def get_pool() -> Optional[AsyncConnectionPool]:
    return _pg_pool


def get_checkpointer() -> Optional[AsyncPostgresSaver]:
    return _checkpointer

def set_tool_registry(registry: ToolRegistry) -> None:
    global _tool_registry
    _tool_registry = registry

def get_tool_registry() -> ToolRegistry:
    return _tool_registry