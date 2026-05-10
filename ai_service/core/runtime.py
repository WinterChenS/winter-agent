from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool


# 运行时全局资源：由 main.py 的 lifespan 初始化，在各路由中按需读取
_pg_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None


def set_runtime(pool: Optional[AsyncConnectionPool], checkpointer: Optional[AsyncPostgresSaver]) -> None:
    global _pg_pool, _checkpointer
    _pg_pool = pool
    _checkpointer = checkpointer


def get_pool() -> Optional[AsyncConnectionPool]:
    return _pg_pool


def get_checkpointer() -> Optional[AsyncPostgresSaver]:
    return _checkpointer

