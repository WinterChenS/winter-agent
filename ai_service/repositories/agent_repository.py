from __future__ import annotations

import json as _json
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

    @abstractmethod
    async def set_enabled(self, agent_id: str, enabled: bool, updated_by: str = "") -> AgentDefinition | None: ...

    @abstractmethod
    async def clone(self, agent_id: str, created_by: str = "") -> AgentDefinition | None: ...


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

    async def set_enabled(self, agent_id: str, enabled: bool, updated_by: str = "") -> AgentDefinition | None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return None
        agent.enabled = enabled
        agent.updated_by = updated_by
        return agent

    async def clone(self, agent_id: str, created_by: str = "") -> AgentDefinition | None:
        import copy as _copy
        import re as _re
        import uuid as _uuid

        source = self._agents.get(agent_id)
        if source is None:
            return None
        cloned = _copy.deepcopy(source)
        cloned.id = _uuid.uuid4().hex[:12]

        # Generate a unique name that doesn't collide with existing agents
        existing_names = {a.name for a in self._agents.values() if a.id != cloned.id}
        match = _re.match(r"^(.*-copy)(\d*)$", cloned.name)
        if match:
            base = match.group(1)
            num = match.group(2)
            new_name = base + (str(int(num) + 1) if num else "2")
        else:
            new_name = cloned.name + "-copy"
        while new_name in existing_names:
            match = _re.match(r"^(.*-copy)(\d*)$", new_name)
            if match:
                base = match.group(1)
                num = match.group(2)
                new_name = base + (str(int(num) + 1) if num else "2")
            else:
                new_name += "-copy"
        cloned.name = new_name

        cloned.display_name += " (Copy)"
        cloned.version = 1
        cloned.is_builtin = False
        cloned.created_by = created_by

        self._agents[cloned.id] = cloned
        return cloned


_AGENT_SELECT = """
    SELECT id, name, display_name, description, system_prompt,
           tools, model_config, trigger_keywords, collaboration_strategy,
           priority, enabled, icon, agent_type, avatar_url, is_builtin,
           tags, metadata, created_by, updated_by, version
    FROM agent_definitions
"""
_AGENT_COLS = ["id", "name", "display_name", "description", "system_prompt",
               "tools", "model_config", "trigger_keywords", "collaboration_strategy",
               "priority", "enabled", "icon", "agent_type", "avatar_url", "is_builtin",
               "tags", "metadata", "created_by", "updated_by", "version"]

def _row_to_agent(row: Any) -> AgentDefinition:
    """Convert a database row to an AgentDefinition."""
    d = dict(zip(_AGENT_COLS, row))
    for field in ("tools", "model_config", "trigger_keywords", "tags", "metadata"):
        if isinstance(d.get(field), str):
            d[field] = _json.loads(d[field])
    # Remove None values so Pydantic uses model defaults for NULL DB columns
    d = {k: v for k, v in d.items() if v is not None}
    return AgentDefinition(**d)


class PostgresAgentRepository(AgentRepository):
    """Postgres-backed repository using psycopg_pool.AsyncConnectionPool."""

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_all(self) -> list[AgentDefinition]:
        async with self._pool.connection() as conn:
            rows = await conn.execute(
                _AGENT_SELECT + " ORDER BY priority DESC"
            )
            records = await rows.fetchall()
            return [_row_to_agent(r) for r in records]

    async def get_by_id(self, agent_id: str) -> AgentDefinition | None:
        async with self._pool.connection() as conn:
            rows = await conn.execute(
                _AGENT_SELECT + " WHERE id = %s", (agent_id,)
            )
            record = await rows.fetchone()
            if record is None:
                return None
            return _row_to_agent(record)

    async def create(self, agent: AgentDefinition) -> AgentDefinition:
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO agent_definitions (id, name, display_name, description,
                    system_prompt, tools, model_config, trigger_keywords,
                    collaboration_strategy, priority, enabled,
                    icon, agent_type, avatar_url, is_builtin,
                    tags, metadata, created_by, updated_by, version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    agent.id, agent.name, agent.display_name, agent.description,
                    agent.system_prompt,
                    _json.dumps(agent.tools), _json.dumps(agent.model_params),
                    _json.dumps(agent.trigger_keywords), agent.collaboration_strategy,
                    agent.priority, agent.enabled,
                    agent.icon, agent.agent_type, agent.avatar_url, agent.is_builtin,
                    _json.dumps(agent.tags), _json.dumps(agent.metadata),
                    agent.created_by, agent.updated_by, agent.version,
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
                    system_prompt = %s, tools = %s, model_config = %s,
                    trigger_keywords = %s, collaboration_strategy = %s,
                    priority = %s, enabled = %s,
                    icon = %s, agent_type = %s, avatar_url = %s, is_builtin = %s,
                    tags = %s, metadata = %s, created_by = %s, updated_by = %s,
                    version = %s
                WHERE id = %s
                """,
                (
                    agent.name, agent.display_name, agent.description,
                    agent.system_prompt,
                    _json.dumps(agent.tools), _json.dumps(agent.model_params),
                    _json.dumps(agent.trigger_keywords), agent.collaboration_strategy,
                    agent.priority, agent.enabled,
                    agent.icon, agent.agent_type, agent.avatar_url, agent.is_builtin,
                    _json.dumps(agent.tags), _json.dumps(agent.metadata),
                    agent.created_by, agent.updated_by, agent.version,
                    agent_id,
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
                _AGENT_SELECT + " WHERE enabled = true ORDER BY priority DESC"
            )
            records = await rows.fetchall()
            return [_row_to_agent(r) for r in records]

    async def set_enabled(self, agent_id: str, enabled: bool, updated_by: str = "") -> AgentDefinition | None:
        async with self._pool.connection() as conn:
            rows = await conn.execute(
                "UPDATE agent_definitions SET enabled = %s, updated_at = NOW(), updated_by = %s WHERE id = %s RETURNING *",
                (enabled, updated_by, agent_id),
            )
            record = await rows.fetchone()
            if record is None:
                return None
            return _row_to_agent(record)

    async def clone(self, agent_id: str, created_by: str = "") -> AgentDefinition | None:
        import re as _re
        import uuid as _uuid

        async with self._pool.connection() as conn:
            rows = await conn.execute(
                _AGENT_SELECT + " WHERE id = %s", (agent_id,)
            )
            source_row = await rows.fetchone()
            if source_row is None:
                return None

            source = _row_to_agent(source_row)

            new_id = _uuid.uuid4().hex[:12]

            # Generate a unique name that doesn't collide with existing agents
            match = _re.match(r"^(.*-copy)(\d*)$", source.name)
            if match:
                base = match.group(1)
                num = match.group(2)
                new_name = base + (str(int(num) + 1) if num else "2")
            else:
                new_name = source.name + "-copy"
            while True:
                check = await conn.execute(
                    "SELECT 1 FROM agent_definitions WHERE name = %s", (new_name,)
                )
                if await check.fetchone() is None:
                    break
                match = _re.match(r"^(.*-copy)(\d*)$", new_name)
                if match:
                    base = match.group(1)
                    num = match.group(2)
                    new_name = base + (str(int(num) + 1) if num else "2")
                else:
                    new_name += "-copy"

            new_display_name = source.display_name + " (Copy)"

            insert_rows = await conn.execute(
                """
                INSERT INTO agent_definitions (id, name, display_name, description,
                    system_prompt, tools, model_config, trigger_keywords,
                    collaboration_strategy, priority, enabled,
                    icon, agent_type, avatar_url, is_builtin,
                    tags, metadata, created_by, updated_by, version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    new_id, new_name, new_display_name, source.description,
                    source.system_prompt,
                    _json.dumps(source.tools), _json.dumps(source.model_params),
                    _json.dumps(source.trigger_keywords), source.collaboration_strategy,
                    source.priority, source.enabled,
                    source.icon, source.agent_type, source.avatar_url, False,
                    _json.dumps(source.tags), _json.dumps(source.metadata),
                    created_by, created_by, 1,
                ),
            )
            record = await insert_rows.fetchone()
            return _row_to_agent(record)
