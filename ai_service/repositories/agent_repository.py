from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from psycopg_pool import AsyncConnectionPool

from models.agent import AgentDefinition


class AgentRepository(ABC):
    """Abstract base repository for AgentDefinition persistence."""

    @abstractmethod
    async def list_all(self) -> list[AgentDefinition]: ...

    @abstractmethod
    async def get_by_id(self, agent_id: str) -> AgentDefinition | None: ...

    @abstractmethod
    async def create(self, agent: AgentDefinition) -> AgentDefinition: ...

    @abstractmethod
    async def update(self, agent_id: str, agent: AgentDefinition) -> AgentDefinition | None: ...

    @abstractmethod
    async def delete(self, agent_id: str) -> bool: ...

    @abstractmethod
    async def list_enabled(self) -> list[AgentDefinition]: ...


class MockAgentRepository(AgentRepository):
    """In-memory mock repository for testing / local development."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentDefinition] = {}

    async def list_all(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    async def get_by_id(self, agent_id: str) -> AgentDefinition | None:
        return self._agents.get(agent_id)

    async def create(self, agent: AgentDefinition) -> AgentDefinition:
        self._agents[agent.id] = agent
        return agent

    async def update(self, agent_id: str, agent: AgentDefinition) -> AgentDefinition | None:
        if agent_id not in self._agents:
            return None
        self._agents[agent_id] = agent
        return agent

    async def delete(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        del self._agents[agent_id]
        return True

    async def list_enabled(self) -> list[AgentDefinition]:
        return [a for a in self._agents.values() if a.enabled]


def _row_to_agent(row: dict[str, Any]) -> AgentDefinition:
    """Convert a database row (dict) to an AgentDefinition."""
    return AgentDefinition(**row)


class PostgresAgentRepository(AgentRepository):
    """Postgres-backed repository using psycopg_pool.AsyncConnectionPool."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_all(self) -> list[AgentDefinition]:
        async with self._pool.connection() as conn:
            rows = await conn.execute(
                "SELECT * FROM agent_definitions ORDER BY priority DESC"
            )
            records = await rows.fetchall()
            return [_row_to_agent(dict(r)) for r in records]

    async def get_by_id(self, agent_id: str) -> AgentDefinition | None:
        async with self._pool.connection() as conn:
            rows = await conn.execute(
                "SELECT * FROM agent_definitions WHERE id = %s", (agent_id,)
            )
            record = await rows.fetchone()
            if record is None:
                return None
            return _row_to_agent(dict(record))

    async def create(self, agent: AgentDefinition) -> AgentDefinition:
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO agent_definitions (id, name, display_name, description,
                    system_prompt, tools, model_params, trigger_keywords,
                    collaboration_strategy, priority, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    agent.id, agent.name, agent.display_name, agent.description,
                    agent.system_prompt, agent.tools, agent.model_params,
                    agent.trigger_keywords, agent.collaboration_strategy,
                    agent.priority, agent.enabled,
                ),
            )
        return agent

    async def update(self, agent_id: str, agent: AgentDefinition) -> AgentDefinition | None:
        async with self._pool.connection() as conn:
            rows = await conn.execute(
                "SELECT 1 FROM agent_definitions WHERE id = %s", (agent_id,)
            )
            if await rows.fetchone() is None:
                return None
            await conn.execute(
                """
                UPDATE agent_definitions SET
                    name = %s, display_name = %s, description = %s,
                    system_prompt = %s, tools = %s, model_params = %s,
                    trigger_keywords = %s, collaboration_strategy = %s,
                    priority = %s, enabled = %s
                WHERE id = %s
                """,
                (
                    agent.name, agent.display_name, agent.description,
                    agent.system_prompt, agent.tools, agent.model_params,
                    agent.trigger_keywords, agent.collaboration_strategy,
                    agent.priority, agent.enabled, agent_id,
                ),
            )
        return agent

    async def delete(self, agent_id: str) -> bool:
        async with self._pool.connection() as conn:
            rows = await conn.execute(
                "DELETE FROM agent_definitions WHERE id = %s RETURNING 1", (agent_id,)
            )
            record = await rows.fetchone()
            return record is not None

    async def list_enabled(self) -> list[AgentDefinition]:
        async with self._pool.connection() as conn:
            rows = await conn.execute(
                "SELECT * FROM agent_definitions WHERE enabled = true ORDER BY priority DESC"
            )
            records = await rows.fetchall()
            return [_row_to_agent(dict(r)) for r in records]
