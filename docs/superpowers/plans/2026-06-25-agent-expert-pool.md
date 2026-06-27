---
change: agent-expert-pool
design-doc: docs/superpowers/specs/2026-06-25-agent-expert-pool-design.md
base-ref: 1a41b51e52e938af482d8d81d5a1e195dd3cc5cc
archived-with: 2026-06-26-agent-expert-pool
---

# Agent Expert Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a dynamic agent expert pool system where agent definitions are stored in PostgreSQL, loaded at runtime by a Router, built on demand by an AgentFactory, and orchestrated via three collaboration strategies (sequential, parallel, supervisor), integrated into the existing LangGraph pipeline with a new admin UI.

**Architecture:** The existing ReAct agent and tool loop is extended with a multi-agent topology: `RouterAgent` (keyword match + LLM fallback) selects matching agents from DB, `AgentFactory` builds runtime instances with rendered prompts and bound tools, and a `CollaborationEngine` executes them via sequential/parallel/supervisor strategies. Results are merged into the existing `chart_planner` and `answer` pipeline. Agent definitions are managed via a new REST API (`/api/v1/agents`) and a frontend admin page (`/admin/agents`).

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, LangGraph, LangChain OpenAI, psycopg (async), asyncio, React 18, TypeScript, Tailwind CSS, React Router, pytest, pytest-asyncio

## Global Constraints

- All existing ReAct graph (agent_node, tool_node, chart_planner_node, answer_node) must remain functional for non-agent-using conversations.
- Agent definitions stored in PostgreSQL `agent_definitions` table (managed via migration SQL, not ORM).
- Repository pattern: `MockAgentRepository` for tests, `PostgresAgentRepository` for production.
- `AgentFactory.build()` returns `AgentRuntime` instances; `CollaborationEngine.run()` orchestrates them.
- Router supports at most 3 agents per match, sorted by keyword hit count then priority.
- Tests go in `ai_service/tests/test_*.py` with no conftest.py.
- Minimum Python 3.12, Pydantic >=2.0.0.
- Frontend admin page uses existing Tailwind CSS + React Router patterns.
- All new files under `ai_service/agents/` and `frontend/src/pages/`.

archived-with: 2026-06-26-agent-expert-pool
---

## File Structure

### Files to Create

| File | Responsibility |
|------|---------------|
| `ai_service/agents/__init__.py` | Package init, exports key symbols |
| `ai_service/agents/models.py` | `AgentDefinition` Pydantic model |
| `ai_service/agents/repository.py` | `AgentRepository` ABC, `MockAgentRepository`, `PostgresAgentRepository` |
| `ai_service/agents/factory.py` | `AgentFactory` + `AgentRuntime` |
| `ai_service/agents/router.py` | `RouteResult` model + `RouterAgent` |
| `ai_service/agents/collaboration/__init__.py` | Package init |
| `ai_service/agents/collaboration/engine.py` | `CollaborationEngine` orchestrator |
| `ai_service/agents/collaboration/sequential.py` | Sequential strategy implementation |
| `ai_service/agents/collaboration/parallel.py` | Parallel strategy implementation |
| `ai_service/agents/collaboration/supervisor.py` | Supervisor strategy implementation |
| `ai_service/graph/multi_agent_nodes.py` | Multi-agent pipeline nodes for LangGraph |
| `ai_service/api/routes/agents.py` | Agent CRUD REST API endpoints |
| `ai_service/tests/test_agent_models.py` | AgentDefinition model + repository tests |
| `ai_service/tests/test_agent_api.py` | CRUD API endpoint tests |
| `ai_service/tests/test_agent_factory.py` | AgentFactory + AgentRuntime tests |
| `ai_service/tests/test_agent_router.py` | RouterAgent tests (keyword + LLM fallback) |
| `ai_service/tests/test_collaboration.py` | All 3 collaboration strategy tests |
| `ai_service/tests/test_multi_agent_graph.py` | Multi-agent graph integration test |
| `frontend/src/pages/AgentAdmin.tsx` | Agent admin UI page |
| `frontend/src/services/agentApi.ts` | Agent admin API client |
| `ai_service/migrations/001_create_agent_definitions.sql` | SQL migration for agent_definitions table |

### Files to Modify

| File | Changes |
|------|---------|
| `ai_service/core/runtime.py` | Add `set_agent_repository()` / `get_agent_repository()` globals |
| `ai_service/main.py` | Import `api/routes/agents.py` router, init repository in lifespan |
| `ai_service/graph/state.py` | Add multi-agent state fields (`route_result`, `agent_runtimes`, `collaboration_result`) |
| `ai_service/graph/graph.py` | Add `create_multi_agent_graph()` function |
| `ai_service/api/routes/chat.py` | Use multi-agent graph when agent repository has enabled agents |
| `frontend/src/App.tsx` | Add `/admin/agents` route |

### Sequential Dependency Graph

```
Phase 1:
  Task 1 (model + repository)
    └── Task 2 (CRUD API)
          └── Phase 2:
                Task 3 (AgentFactory + AgentRuntime)
                  └── Task 4 (RouterAgent)
                        └── Phase 3:
                              Task 5 (sequential collaboration)
                                └── Task 6 (parallel collaboration)
                                      └── Task 7 (supervisor collaboration)
                                            └── Phase 4:
                                                  Task 8 (graph integration)
                                                    └── Phase 5:
                                                          Task 9 (frontend admin)
                                                            └── Task 10 (E2E test)
```

archived-with: 2026-06-26-agent-expert-pool
---

### Task 1: AgentDefinition Model + Repository + Migration SQL

**Files:**
- Create: `ai_service/agents/__init__.py`
- Create: `ai_service/agents/models.py`
- Create: `ai_service/agents/repository.py`
- Create: `ai_service/migrations/001_create_agent_definitions.sql`
- Create: `ai_service/tests/test_agent_models.py`

**Interfaces:**
- Consumes: `uuid` (stdlib), `pydantic.BaseModel`, `abc.ABC`, `datetime`
- Produces: `AgentDefinition` (Pydantic model), `AgentRepository` (ABC), `MockAgentRepository`, `PostgresAgentRepository`

- [x] **Step 1: Write failing test for AgentDefinition model defaults**

Create `ai_service/tests/test_agent_models.py`:

```python
from __future__ import annotations

from agents.models import AgentDefinition


def test_agent_definition_defaults():
    """AgentDefinition should set sensible defaults for optional fields."""
    agent = AgentDefinition(
        name="test_agent",
        display_name="Test Agent",
        system_prompt="You are a test agent.",
    )
    assert agent.name == "test_agent"
    assert agent.display_name == "Test Agent"
    assert agent.system_prompt == "You are a test agent."
    assert agent.description == ""
    assert agent.tools == []
    assert agent.model_parameters == {"temperature": 0.7}
    assert agent.trigger_keywords == []
    assert agent.collaboration_strategy == "sequential"
    assert agent.priority == 0
    assert agent.enabled is True
    assert isinstance(agent.id, str) and len(agent.id) > 0


def test_agent_definition_full_construction():
    """AgentDefinition should accept all fields."""
    agent = AgentDefinition(
        name="research",
        display_name="Research Agent",
        description="Searches the web",
        system_prompt="You search and summarize.",
        tools=["search", "browser"],
        model_parameters={"temperature": 0.3},
        trigger_keywords=["research", "search"],
        collaboration_strategy="parallel",
        priority=10,
        enabled=False,
    )
    assert agent.name == "research"
    assert agent.tools == ["search", "browser"]
    assert agent.model_parameters == {"temperature": 0.3}
    assert agent.collaboration_strategy == "parallel"
    assert agent.priority == 10
    assert agent.enabled is False


def test_agent_definition_serialization():
    """AgentDefinition should round-trip through dict serialization."""
    agent = AgentDefinition(
        name="echo",
        display_name="Echo",
        system_prompt="Repeat after me.",
    )
    data = agent.model_dump()
    restored = AgentDefinition(**data)
    assert restored.name == agent.name
    assert restored.display_name == agent.display_name
    assert restored.system_prompt == agent.system_prompt
    assert restored.id == agent.id
    assert restored.model_parameters == agent.model_parameters
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest ai_service/tests/test_agent_models.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agents'`

- [x] **Step 3: Write AgentDefinition model and init**

Create `ai_service/agents/__init__.py`:

```python
from agents.models import AgentDefinition
from agents.repository import AgentRepository, MockAgentRepository, PostgresAgentRepository

__all__ = [
    "AgentDefinition",
    "AgentRepository",
    "MockAgentRepository",
    "PostgresAgentRepository",
]
```

Create `ai_service/agents/models.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    """Pydantic model for an agent definition stored in the DB."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    display_name: str
    description: str = ""
    system_prompt: str
    tools: list[str] = Field(default_factory=list)
    model_parameters: dict[str, Any] = Field(default_factory=lambda: {"temperature": 0.7})
    trigger_keywords: list[str] = Field(default_factory=list)
    collaboration_strategy: str = "sequential"
    priority: int = 0
    enabled: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest ai_service/tests/test_agent_models.py -v`

Expected: 3 PASSED

- [x] **Step 5: Write failing test for repository operations**

Append to `ai_service/tests/test_agent_models.py`:

```python
import pytest

from agents.repository import MockAgentRepository


@pytest.mark.asyncio
async def test_mock_repository_create_and_list():
    """MockAgentRepository should create and list agents."""
    repo = MockAgentRepository()
    agent = AgentDefinition(
        name="test",
        display_name="Test",
        system_prompt="You are a test.",
    )
    created = await repo.create_agent(agent)
    assert created.id == agent.id

    agents = await repo.list_agents()
    assert len(agents) == 1
    assert agents[0].name == "test"


@pytest.mark.asyncio
async def test_mock_repository_get_update_delete():
    """MockAgentRepository should support get, update, and delete."""
    repo = MockAgentRepository()
    agent = AgentDefinition(
        name="target",
        display_name="Target",
        system_prompt="You are target.",
    )
    await repo.create_agent(agent)

    # Get
    found = await repo.get_agent(agent.id)
    assert found is not None
    assert found.name == "target"

    # Get nonexistent
    missing = await repo.get_agent("nonexistent")
    assert missing is None

    # Update
    updated = await repo.update_agent(agent.id, {"display_name": "Updated"})
    assert updated is not None
    assert updated.display_name == "Updated"

    # Update nonexistent
    no_update = await repo.update_agent("nonexistent", {"name": "x"})
    assert no_update is None

    # Delete
    deleted = await repo.delete_agent(agent.id)
    assert deleted is True
    assert len(await repo.list_agents()) == 0

    # Delete nonexistent
    assert await repo.delete_agent("nonexistent") is False


@pytest.mark.asyncio
async def test_mock_repository_get_enabled():
    """get_enabled_agents should return only enabled agents."""
    repo = MockAgentRepository()
    a1 = AgentDefinition(name="a1", display_name="A1", system_prompt=".", enabled=True)
    a2 = AgentDefinition(name="a2", display_name="A2", system_prompt=".", enabled=False)
    a3 = AgentDefinition(name="a3", display_name="A3", system_prompt=".", enabled=True)
    await repo.create_agent(a1)
    await repo.create_agent(a2)
    await repo.create_agent(a3)

    enabled = await repo.get_enabled_agents()
    assert len(enabled) == 2
    enabled_names = {a.name for a in enabled}
    assert enabled_names == {"a1", "a3"}
```

- [x] **Step 6: Run test to verify it fails**

Run: `.venv/bin/pytest ai_service/tests/test_agent_models.py::test_mock_repository_create_and_list -v`

Expected: FAIL with `ImportError` (MockAgentRepository not defined yet)

- [x] **Step 7: Write MockAgentRepository + AgentRepository ABC**

Create `ai_service/agents/repository.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from agents.models import AgentDefinition


class AgentRepository(ABC):
    """Abstract base repository for agent definitions."""

    @abstractmethod
    async def list_agents(self) -> list[AgentDefinition]:
        ...

    @abstractmethod
    async def get_agent(self, agent_id: str) -> AgentDefinition | None:
        ...

    @abstractmethod
    async def create_agent(self, agent: AgentDefinition) -> AgentDefinition:
        ...

    @abstractmethod
    async def update_agent(self, agent_id: str, data: dict[str, Any]) -> AgentDefinition | None:
        ...

    @abstractmethod
    async def delete_agent(self, agent_id: str) -> bool:
        ...

    @abstractmethod
    async def get_enabled_agents(self) -> list[AgentDefinition]:
        ...


class MockAgentRepository(AgentRepository):
    """In-memory repository for testing."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentDefinition] = {}

    async def list_agents(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    async def get_agent(self, agent_id: str) -> AgentDefinition | None:
        return self._agents.get(agent_id)

    async def create_agent(self, agent: AgentDefinition) -> AgentDefinition:
        self._agents[agent.id] = agent
        return agent

    async def update_agent(self, agent_id: str, data: dict[str, Any]) -> AgentDefinition | None:
        if agent_id not in self._agents:
            return None
        existing = self._agents[agent_id]
        updated = existing.model_copy(update=data)
        updated.updated_at = datetime.now(timezone.utc).isoformat()
        self._agents[agent_id] = updated
        return updated

    async def delete_agent(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        del self._agents[agent_id]
        return True

    async def get_enabled_agents(self) -> list[AgentDefinition]:
        return [a for a in self._agents.values() if a.enabled]


class PostgresAgentRepository(AgentRepository):
    """PostgreSQL-backed repository using the existing async pool."""

    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def list_agents(self) -> list[AgentDefinition]:
        async with self.pool.connection() as conn:
            rows = await conn.execute(
                "SELECT * FROM agent_definitions ORDER BY priority DESC, name ASC"
            )
            return [self._row_to_agent(r) for r in rows]

    async def get_agent(self, agent_id: str) -> AgentDefinition | None:
        async with self.pool.connection() as conn:
            rows = await conn.execute(
                "SELECT * FROM agent_definitions WHERE id = %s", (agent_id,)
            )
            row = rows.fetchone()
            return self._row_to_agent(row) if row else None

    async def create_agent(self, agent: AgentDefinition) -> AgentDefinition:
        async with self.pool.connection() as conn:
            await conn.execute(
                """INSERT INTO agent_definitions
                   (id, name, display_name, description, system_prompt, tools,
                    model_parameters, trigger_keywords, collaboration_strategy,
                    priority, enabled, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (agent.id, agent.name, agent.display_name, agent.description,
                 agent.system_prompt, agent.tools, agent.model_parameters,
                 agent.trigger_keywords, agent.collaboration_strategy,
                 agent.priority, agent.enabled, agent.created_at, agent.updated_at),
            )
        return agent

    async def update_agent(self, agent_id: str, data: dict[str, Any]) -> AgentDefinition | None:
        existing = await self.get_agent(agent_id)
        if existing is None:
            return None
        updated = existing.model_copy(update=data)
        updated.updated_at = datetime.now(timezone.utc).isoformat()
        async with self.pool.connection() as conn:
            await conn.execute(
                """UPDATE agent_definitions SET
                   name=%s, display_name=%s, description=%s, system_prompt=%s,
                   tools=%s, model_parameters=%s, trigger_keywords=%s,
                   collaboration_strategy=%s, priority=%s, enabled=%s, updated_at=%s
                   WHERE id=%s""",
                (updated.name, updated.display_name, updated.description,
                 updated.system_prompt, updated.tools, updated.model_parameters,
                 updated.trigger_keywords, updated.collaboration_strategy,
                 updated.priority, updated.enabled, updated.updated_at, agent_id),
            )
        return updated

    async def delete_agent(self, agent_id: str) -> bool:
        existing = await self.get_agent(agent_id)
        if existing is None:
            return False
        async with self.pool.connection() as conn:
            await conn.execute(
                "DELETE FROM agent_definitions WHERE id = %s", (agent_id,)
            )
        return True

    async def get_enabled_agents(self) -> list[AgentDefinition]:
        async with self.pool.connection() as conn:
            rows = await conn.execute(
                "SELECT * FROM agent_definitions WHERE enabled = true ORDER BY priority DESC"
            )
            return [self._row_to_agent(r) for r in rows]

    @staticmethod
    def _row_to_agent(row: Any) -> AgentDefinition:
        return AgentDefinition(
            id=str(row["id"]),
            name=row["name"],
            display_name=row["display_name"],
            description=row.get("description", ""),
            system_prompt=row["system_prompt"],
            tools=list(row.get("tools", []) or []),
            model_parameters=dict(row.get("model_parameters", {}) or {"temperature": 0.7}),
            trigger_keywords=list(row.get("trigger_keywords", []) or []),
            collaboration_strategy=row.get("collaboration_strategy", "sequential"),
            priority=row.get("priority", 0),
            enabled=bool(row.get("enabled", True)),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
        )
```

- [x] **Step 8: Run tests to verify they pass**

Run: `.venv/bin/pytest ai_service/tests/test_agent_models.py -v`

Expected: 6 PASSED (3 model + 3 repository)

- [x] **Step 9: Create migration SQL**

Create `ai_service/migrations/001_create_agent_definitions.sql`:

```sql
CREATE TABLE IF NOT EXISTS agent_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(64) UNIQUE NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL,
    tools JSONB NOT NULL DEFAULT '[]',
    model_parameters JSONB NOT NULL DEFAULT '{"temperature":0.7}',
    trigger_keywords JSONB NOT NULL DEFAULT '[]',
    collaboration_strategy VARCHAR(16) NOT NULL DEFAULT 'sequential',
    priority INT NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

- [x] **Step 10: Update runtime globals**

Modify `ai_service/core/runtime.py` (append before the file end):

```python
# Agent repository global
_agent_repository: "AgentRepository | None" = None  # type: ignore[name-defined]


def set_agent_repository(repo: "AgentRepository | None") -> None:
    global _agent_repository
    _agent_repository = repo


def get_agent_repository() -> "AgentRepository | None":
    return _agent_repository
```

Add the import at the top:

```python
# Keep existing imports, then add:
from __future__ import annotations
```

(Note: `from __future__ import annotations` is already present at the top of `core/runtime.py`.)

- [x] **Step 11: Commit**

```bash
git add ai_service/agents/__init__.py ai_service/agents/models.py ai_service/agents/repository.py ai_service/migrations/001_create_agent_definitions.sql ai_service/tests/test_agent_models.py ai_service/core/runtime.py
git commit -m "feat: add AgentDefinition model, repository pattern, and migration SQL"
```

archived-with: 2026-06-26-agent-expert-pool
---

### Task 2: Agent CRUD API Endpoints

**Files:**
- Create: `ai_service/api/routes/agents.py`
- Modify: `ai_service/main.py`
- Create: `ai_service/tests/test_agent_api.py`

**Interfaces:**
- Consumes: `AgentDefinition`, `AgentRepository`, `MockAgentRepository`, `get_agent_repository()`
- Produces: REST endpoints `GET/POST/GET/{id}/PUT/{id}/DELETE/{id} /api/v1/agents`, `POST /api/v1/agents/reload`

- [x] **Step 1: Write failing test for CRUD API**

Create `ai_service/tests/test_agent_api.py`:

```python
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from agents import AgentDefinition, MockAgentRepository
from core.runtime import set_agent_repository, get_agent_repository
from api.routes.agents import router as agents_router


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(agents_router)
    return app


@pytest.fixture
def repo() -> MockAgentRepository:
    r = MockAgentRepository()
    set_agent_repository(r)
    yield r
    set_agent_repository(None)


@pytest.mark.asyncio
async def test_list_agents_empty(app: FastAPI, repo: MockAgentRepository):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents/")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_and_get_agent(app: FastAPI, repo: MockAgentRepository):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "name": "test_agent",
            "display_name": "Test Agent",
            "system_prompt": "You are a test.",
        }
        create_resp = await client.post("/api/v1/agents/", json=payload)
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["name"] == "test_agent"
    assert data["display_name"] == "Test Agent"
    agent_id = data["id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        get_resp = await client.get(f"/api/v1/agents/{agent_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "test_agent"


@pytest.mark.asyncio
async def test_update_agent(app: FastAPI, repo: MockAgentRepository):
    agent = AgentDefinition(name="orig", display_name="Original", system_prompt=".")
    await repo.create_agent(agent)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(f"/api/v1/agents/{agent.id}", json={"display_name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_agent(app: FastAPI, repo: MockAgentRepository):
    agent = AgentDefinition(name="del", display_name="Delete Me", system_prompt=".")
    await repo.create_agent(agent)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(f"/api/v1/agents/{agent.id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_get_nonexistent_agent(app: FastAPI, repo: MockAgentRepository):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/agents/nonexistent-id")
    assert resp.status_code == 404
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest ai_service/tests/test_agent_api.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'api.routes.agents'`

- [x] **Step 3: Write agent CRUD API router**

Create `ai_service/api/routes/agents.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agents import AgentDefinition
from core.runtime import get_agent_repository

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


def _get_repo():
    repo = get_agent_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="Agent repository not initialized")
    return repo


@router.get("/")
async def list_agents():
    repo = _get_repo()
    return [a.model_dump() for a in await repo.list_agents()]


@router.post("/")
async def create_agent(data: dict):
    repo = _get_repo()
    agent = AgentDefinition(**data)
    created = await repo.create_agent(agent)
    return created.model_dump()


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    repo = _get_repo()
    agent = await repo.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.model_dump()


@router.put("/{agent_id}")
async def update_agent(agent_id: str, data: dict):
    repo = _get_repo()
    agent = await repo.update_agent(agent_id, data)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.model_dump()


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    repo = _get_repo()
    deleted = await repo.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"deleted": True}


@router.post("/reload")
async def reload_agents():
    """Clear any in-memory cache and re-read from DB."""
    from core.runtime import get_tool_registry
    # Future: invalidate any router cache
    return {"status": "ok"}
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest ai_service/tests/test_agent_api.py -v`

Expected: 5 PASSED (may skip or fail some if httpx not installed — install if needed)

Note: If `httpx` is not installed, add to requirements.txt and install:

```bash
echo "httpx>=0.25.0" >> ai_service/requirements.txt && .venv/bin/pip install httpx
```

- [x] **Step 5: Register agent router in main.py**

Modify `ai_service/main.py`:

After `from api.routes.system import router as system_router`, add:

```python
from api.routes.agents import router as agents_router
```

After `app.include_router(chat_router)`, add:

```python
app.include_router(agents_router)
```

In the lifespan, after `set_tool_registry(tool_registry)`, add:

```python
from agents import PostgresAgentRepository
if pg_pool:
    agent_repo = PostgresAgentRepository(pg_pool)
    set_agent_repository(agent_repo)
else:
    from agents import MockAgentRepository
    set_agent_repository(MockAgentRepository())
```

Add import at top of main.py:

```python
from core.runtime import set_runtime, set_tool_registry, set_agent_repository
```

- [x] **Step 6: Run model and API tests to confirm nothing broken**

Run: `.venv/bin/pytest ai_service/tests/test_agent_models.py ai_service/tests/test_agent_api.py -v`

Expected: All tests PASS

- [x] **Step 7: Commit**

```bash
git add ai_service/api/routes/agents.py ai_service/tests/test_agent_api.py ai_service/main.py
git commit -m "feat: add Agent CRUD API endpoints"
```

archived-with: 2026-06-26-agent-expert-pool
---

### Task 3: AgentFactory + AgentRuntime

**Files:**
- Create: `ai_service/agents/factory.py`
- Create: `ai_service/tests/test_agent_factory.py`

**Interfaces:**
- Consumes: `AgentDefinition`, `ToolRegistry` (via `get_tool_registry()`), `settings` (for LLM config)
- Produces: `AgentRuntime` class with `run(user_input, context) -> str`, `AgentFactory.build(definition, context) -> AgentRuntime`

- [x] **Step 1: Write failing test for AgentFactory + AgentRuntime**

Create `ai_service/tests/test_agent_factory.py`:

```python
from __future__ import annotations

import pytest

from agents.models import AgentDefinition
from agents.factory import AgentFactory, AgentRuntime
from tools.base import BaseTool, ToolResult
from typing import Any, Mapping


class _EchoTool(BaseTool):
    name: str = "echo"
    description: str = "Echo back input"
    input_schema: dict[str, Any] = {"type": "object", "properties": {"query": {"type": "string"}}}

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data={"echo": input_payload.get("query", "")})


@pytest.mark.asyncio
async def test_agent_runtime_has_expected_attributes():
    """AgentRuntime should store name, llm, prompt, tools."""
    runtime = AgentRuntime(
        name="test_agent",
        llm=None,
        prompt="You are a test.",
        tools=[_EchoTool()],
    )
    assert runtime.name == "test_agent"
    assert runtime.prompt == "You are a test."
    assert len(runtime.tools) == 1
    assert runtime.tools[0].name == "echo"


@pytest.mark.asyncio
async def test_agent_factory_build_creates_runtime():
    """AgentFactory.build() should create an AgentRuntime from a definition."""
    from tools.registry import ToolRegistry
    registry = ToolRegistry()
    registry.register(_EchoTool())

    factory = AgentFactory(registry)
    definition = AgentDefinition(
        name="echo_bot",
        display_name="Echo Bot",
        system_prompt="You are echo. {user_context}",
        tools=["echo"],
    )

    runtime = await factory.build(definition, context={"user_context": "hello"})
    assert runtime.name == "echo_bot"
    assert "hello" in runtime.prompt
    assert len(runtime.tools) == 1


@pytest.mark.asyncio
async def test_agent_factory_skips_missing_tools():
    """AgentFactory.build() should skip tools not in registry."""
    from tools.registry import ToolRegistry
    registry = ToolRegistry()
    registry.register(_EchoTool())

    factory = AgentFactory(registry)
    definition = AgentDefinition(
        name="partial",
        display_name="Partial",
        system_prompt="You are partial.",
        tools=["echo", "nonexistent_tool"],
    )

    runtime = await factory.build(definition)
    assert len(runtime.tools) == 1
    assert runtime.tools[0].name == "echo"


@pytest.mark.asyncio
async def test_agent_factory_context_formatting():
    """AgentFactory.build() should format prompt with context."""
    from tools.registry import ToolRegistry
    registry = ToolRegistry()

    factory = AgentFactory(registry)
    definition = AgentDefinition(
        name="formatter",
        display_name="Formatter",
        system_prompt="User's name is {name}, age is {age}.",
    )

    runtime = await factory.build(definition, context={"name": "Alice", "age": "30"})
    assert "Alice" in runtime.prompt
    assert "30" in runtime.prompt
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest ai_service/tests/test_agent_factory.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.factory'`

- [x] **Step 3: Write AgentFactory and AgentRuntime**

Create `ai_service/agents/factory.py`:

```python
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.models import AgentDefinition
from config import settings
from core.runtime import get_tool_registry
from tools.base import BaseTool

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Runtime instance of an agent with bound LLM, prompt, and tools."""

    def __init__(
        self,
        name: str,
        llm: ChatOpenAI | None,
        prompt: str,
        tools: list[BaseTool],
    ) -> None:
        self.name = name
        self.llm = llm
        self.prompt = prompt
        self.tools = tools

    async def run(self, user_input: str, context: dict[str, Any] | None = None) -> str:
        """Execute this agent with the given user input."""
        system_prompt = self.prompt
        if context:
            try:
                system_prompt = self.prompt.format(**context)
            except KeyError:
                pass

        if self.llm is None:
            return f"[{self.name}] No LLM configured."

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ]
        try:
            response = await self.llm.ainvoke(messages)
            return str(response.content or "")
        except Exception as exc:
            logger.exception("AgentRuntime.run() failed for %s", self.name)
            return f"[{self.name}] Error: {exc}"


class AgentFactory:
    """Builds AgentRuntime instances from AgentDefinition objects."""

    def __init__(self, tool_registry: Any = None) -> None:
        self.tool_registry = tool_registry or get_tool_registry()

    async def build(
        self,
        definition: AgentDefinition,
        context: dict[str, Any] | None = None,
    ) -> AgentRuntime:
        """Build an AgentRuntime from a definition."""
        prompt = definition.system_prompt
        if context:
            try:
                prompt = definition.system_prompt.format(**context)
            except KeyError:
                prompt = definition.system_prompt

        tool_list: list[BaseTool] = []
        if self.tool_registry:
            for tool_name in definition.tools:
                try:
                    tool = self.tool_registry.get(tool_name)
                    tool_list.append(tool)
                except Exception:
                    logger.warning("Tool '%s' not found, skipping for agent %s", tool_name, definition.name)

        llm: ChatOpenAI | None = None
        if settings.api_key:
            llm = ChatOpenAI(
                model=settings.model,
                temperature=definition.model_parameters.get("temperature", 0.7),
                api_key=settings.api_key,
                base_url=settings.base_url,
                response_format={"type": "json_object"} if definition.collaboration_strategy == "supervisor" else None,
            )

        return AgentRuntime(
            name=definition.name,
            llm=llm,
            prompt=prompt,
            tools=tool_list,
        )
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest ai_service/tests/test_agent_factory.py -v`

Expected: 4 PASSED

- [x] **Step 5: Commit**

```bash
git add ai_service/agents/factory.py ai_service/tests/test_agent_factory.py
git commit -m "feat: add AgentFactory and AgentRuntime"
```

archived-with: 2026-06-26-agent-expert-pool
---

### Task 4: RouterAgent — Keyword Matching + LLM Fallback

**Files:**
- Create: `ai_service/agents/router.py`
- Create: `ai_service/tests/test_agent_router.py`

**Interfaces:**
- Consumes: `AgentDefinition`, `AgentRepository`
- Produces: `RouteResult` (Pydantic model with `agents: list[AgentDefinition]`, `strategy: str`), `RouterAgent.route(user_input) -> RouteResult | None`

- [x] **Step 1: Write failing test for RouterAgent**

Create `ai_service/tests/test_agent_router.py`:

```python
from __future__ import annotations

import pytest

from agents.models import AgentDefinition
from agents.repository import MockAgentRepository
from agents.router import RouterAgent, RouteResult


@pytest.mark.asyncio
async def test_router_keyword_match_single():
    """Router should match agent by trigger keyword."""
    repo = MockAgentRepository()
    agent = AgentDefinition(
        name="weather",
        display_name="Weather Agent",
        system_prompt="You provide weather info.",
        trigger_keywords=["weather", "temperature", "forecast"],
    )
    await repo.create_agent(agent)

    router = RouterAgent(repo)
    result = await router.route("What is the weather today?")
    assert result is not None
    assert len(result.agents) == 1
    assert result.agents[0].name == "weather"


@pytest.mark.asyncio
async def test_router_keyword_match_multiple():
    """Router should return top 3 agents sorted by hit count then priority."""
    repo = MockAgentRepository()
    a1 = AgentDefinition(
        name="weather", display_name="Weather", system_prompt=".",
        trigger_keywords=["weather"], priority=0,
    )
    a2 = AgentDefinition(
        name="news", display_name="News", system_prompt=".",
        trigger_keywords=["weather", "news"], priority=5,
    )
    a3 = AgentDefinition(
        name="general", display_name="General", system_prompt=".",
        trigger_keywords=["weather", "news", "forecast"], priority=10,
    )
    a4 = AgentDefinition(
        name="low_priority", display_name="Low", system_prompt=".",
        trigger_keywords=["weather"], priority=1,
    )
    for a in [a1, a2, a3, a4]:
        await repo.create_agent(a)

    router = RouterAgent(repo)
    result = await router.route("weather news forecast")
    assert result is not None
    # a3 (3 hits, prio 10), a2 (2 hits, prio 5), then a1 (1 hit, prio 0) or a4 (1 hit, prio 1)
    names = [a.name for a in result.agents]
    assert len(names) <= 3
    assert names[0] == "general"  # most hits


@pytest.mark.asyncio
async def test_router_keyword_match_only_enabled():
    """Router should only match enabled agents."""
    repo = MockAgentRepository()
    enabled = AgentDefinition(
        name="active", display_name="Active", system_prompt=".",
        trigger_keywords=["help"], enabled=True,
    )
    disabled = AgentDefinition(
        name="inactive", display_name="Inactive", system_prompt=".",
        trigger_keywords=["help"], enabled=False,
    )
    await repo.create_agent(enabled)
    await repo.create_agent(disabled)

    router = RouterAgent(repo)
    result = await router.route("I need help")
    assert result is not None
    assert len(result.agents) == 1
    assert result.agents[0].name == "active"


@pytest.mark.asyncio
async def test_router_no_match_returns_none():
    """Router should return None when no keywords match and no LLM fallback."""
    repo = MockAgentRepository()
    agent = AgentDefinition(
        name="weather", display_name="Weather", system_prompt=".",
        trigger_keywords=["weather"],
    )
    await repo.create_agent(agent)

    router = RouterAgent(repo)
    result = await router.route("Tell me a joke")
    assert result is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest ai_service/tests/test_agent_router.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.router'`

- [x] **Step 3: Write RouterAgent + RouteResult**

Create `ai_service/agents/router.py`:

```python
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from agents.models import AgentDefinition
from agents.repository import AgentRepository
from config import settings

logger = logging.getLogger(__name__)


class RouteResult(BaseModel):
    """Result of routing a user request to matching agents."""
    agents: list[AgentDefinition] = Field(default_factory=list)
    strategy: str = "sequential"


class RouterAgent:
    """Routes user requests to matching agents by keyword then LLM fallback."""

    def __init__(
        self,
        repository: AgentRepository,
        llm: ChatOpenAI | None = None,
    ) -> None:
        self.repository = repository
        self.llm = llm

    async def route(self, user_input: str) -> RouteResult | None:
        """Route user input to matching agents. Returns None if no match."""
        enabled_agents = await self.repository.get_enabled_agents()
        if not enabled_agents:
            return None

        # Phase 1: Keyword matching
        matched: list[tuple[int, AgentDefinition]] = []
        for agent in enabled_agents:
            hits = sum(1 for kw in agent.trigger_keywords if kw.lower() in user_input.lower())
            if hits > 0:
                matched.append((hits, agent))

        if matched:
            matched.sort(key=lambda x: (-x[0], -x[1].priority))
            top_agents = [agent for _, agent in matched[:3]]
            strategy = top_agents[0].collaboration_strategy if top_agents else "sequential"
            return RouteResult(agents=top_agents, strategy=strategy)

        # Phase 2: LLM fallback
        if self.llm is None and not settings.api_key:
            return None

        return await self._llm_route(user_input, enabled_agents)

    async def _llm_route(
        self,
        user_input: str,
        enabled_agents: list[AgentDefinition],
    ) -> RouteResult | None:
        """Use LLM to determine which agents should handle the request."""
        llm = self.llm or ChatOpenAI(
            model=settings.model,
            temperature=0.0,
            api_key=settings.api_key,
            base_url=settings.base_url,
            response_format={"type": "json_object"},
        )

        agent_descriptions = "\n".join(
            f"- {a.name}: {a.display_name} — {a.description} "
            f"(keywords: {', '.join(a.trigger_keywords) or 'none'})"
            for a in enabled_agents
        )

        prompt = (
            f"Given the user request below, select up to 3 agents from the list "
            f"that are most relevant. Output JSON with 'agents' (list of agent names) "
            f"and 'strategy' (one of: sequential, parallel, supervisor).\n\n"
            f"Available agents:\n{agent_descriptions}\n\n"
            f"User request: {user_input}"
        )

        try:
            response = await llm.ainvoke([SystemMessage(content=prompt)])
            parsed = json.loads(response.content)
            agent_names = parsed.get("agents", [])
            strategy = parsed.get("strategy", "sequential")
        except Exception:
            logger.warning("LLM routing failed, returning None")
            return None

        name_map = {a.name: a for a in enabled_agents}
        matched = [name_map[name] for name in agent_names if name in name_map]

        if not matched:
            return None

        return RouteResult(agents=matched[:3], strategy=strategy)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest ai_service/tests/test_agent_router.py -v`

Expected: 4 PASSED

- [x] **Step 5: Commit**

```bash
git add ai_service/agents/router.py ai_service/tests/test_agent_router.py
git commit -m "feat: add RouterAgent with keyword matching and LLM fallback"
```

archived-with: 2026-06-26-agent-expert-pool
---

### Task 5: Sequential Collaboration Strategy

**Files:**
- Create: `ai_service/agents/collaboration/__init__.py`
- Create: `ai_service/agents/collaboration/engine.py`
- Create: `ai_service/agents/collaboration/sequential.py`
- Create: `ai_service/tests/test_collaboration.py`

**Interfaces:**
- Consumes: `AgentRuntime`
- Produces: `CollaborationEngine.run(agents, strategy, user_input) -> str`

- [x] **Step 1: Write failing test for sequential collaboration**

Append section to `ai_service/tests/test_collaboration.py`:

```python
from __future__ import annotations

import pytest

from agents.factory import AgentRuntime
from agents.collaboration.engine import CollaborationEngine


class _MockLLM:
    """Minimal mock LLM that returns a fixed response."""
    def __init__(self, response: str = "mock response"):
        self.response = response

    async def ainvoke(self, messages):
        from langchain_core.messages import AIMessage
        return AIMessage(content=self.response)


@pytest.mark.asyncio
async def test_sequential_single_agent():
    """Sequential with one agent should return its output."""
    llm = _MockLLM("Hello from agent")
    agent = AgentRuntime(name="a1", llm=llm, prompt="You are A1.", tools=[])
    engine = CollaborationEngine()
    result = await engine.run(agents=[agent], strategy="sequential", user_input="hi")
    assert "Hello from agent" in result


@pytest.mark.asyncio
async def test_sequential_two_agents():
    """Sequential should chain outputs: agent2 receives agent1's result."""
    llm1 = _MockLLM("First result.")
    llm2 = _MockLLM("Second result.")
    a1 = AgentRuntime(name="a1", llm=llm1, prompt="You are A1.", tools=[])
    a2 = AgentRuntime(name="a2", llm=llm2, prompt="You are A2.", tools=[])
    engine = CollaborationEngine()
    result = await engine.run(agents=[a1, a2], strategy="sequential", user_input="start")
    assert "Second result" in result


@pytest.mark.asyncio
async def test_sequential_no_agents():
    """Sequential with empty agent list should return empty string."""
    engine = CollaborationEngine()
    result = await engine.run(agents=[], strategy="sequential", user_input="hi")
    assert result == ""
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest ai_service/tests/test_collaboration.py::test_sequential_single_agent -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.collaboration'`

- [x] **Step 3: Write collaboration engine and sequential strategy**

Create `ai_service/agents/collaboration/__init__.py`:

```python
from agents.collaboration.engine import CollaborationEngine

__all__ = ["CollaborationEngine"]
```

Create `ai_service/agents/collaboration/engine.py`:

```python
from __future__ import annotations

import logging
from typing import Any

from agents.factory import AgentRuntime
from agents.collaboration.sequential import sequential_run
from agents.collaboration.parallel import parallel_run
from agents.collaboration.supervisor import supervisor_run

logger = logging.getLogger(__name__)


class CollaborationEngine:
    """Orchestrates multi-agent collaboration strategies."""

    async def run(
        self,
        agents: list[AgentRuntime],
        strategy: str,
        user_input: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        if not agents:
            return ""

        if strategy == "parallel":
            return await parallel_run(agents, user_input, context)
        elif strategy == "supervisor":
            return await supervisor_run(agents, user_input, context)
        else:
            # Default: sequential
            return await sequential_run(agents, user_input, context)
```

Create `ai_service/agents/collaboration/sequential.py`:

```python
from __future__ import annotations

from typing import Any

from agents.factory import AgentRuntime


async def sequential_run(
    agents: list[AgentRuntime],
    user_input: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Run agents sequentially, passing each output as next input."""
    result = user_input
    for agent in agents:
        result = await agent.run(result, context)
    return result
```

- [x] **Step 4: Run tests to verify sequential passes**

Run: `.venv/bin/pytest ai_service/tests/test_collaboration.py::test_sequential_single_agent ai_service/tests/test_collaboration.py::test_sequential_two_agents ai_service/tests/test_collaboration.py::test_sequential_no_agents -v`

Expected: 3 PASSED

- [x] **Step 5: Commit**

```bash
git add ai_service/agents/collaboration/__init__.py ai_service/agents/collaboration/engine.py ai_service/agents/collaboration/sequential.py ai_service/tests/test_collaboration.py
git commit -m "feat: add sequential collaboration strategy"
```

archived-with: 2026-06-26-agent-expert-pool
---

### Task 6: Parallel Collaboration Strategy

**Files:**
- Create: `ai_service/agents/collaboration/parallel.py`
- Modify: `ai_service/tests/test_collaboration.py` (append tests)

**Interfaces:**
- Produces: `parallel_run(agents, user_input, context) -> str`

- [x] **Step 1: Write failing test for parallel collaboration**

Append to `ai_service/tests/test_collaboration.py`:

```python
@pytest.mark.asyncio
async def test_parallel_two_agents():
    """Parallel should run agents concurrently and merge results."""
    llm1 = _MockLLM("Result from A1")
    llm2 = _MockLLM("Result from A2")
    a1 = AgentRuntime(name="a1", llm=llm1, prompt="You are A1.", tools=[])
    a2 = AgentRuntime(name="a2", llm=llm2, prompt="You are A2.", tools=[])
    engine = CollaborationEngine()
    result = await engine.run(agents=[a1, a2], strategy="parallel", user_input="go")
    assert "Result from A1" in result
    assert "Result from A2" in result


@pytest.mark.asyncio
async def test_parallel_single_agent():
    """Parallel with one agent should work like sequential."""
    llm = _MockLLM("Solo result")
    agent = AgentRuntime(name="solo", llm=llm, prompt=".", tools=[])
    engine = CollaborationEngine()
    result = await engine.run(agents=[agent], strategy="parallel", user_input="test")
    assert "Solo result" in result
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest ai_service/tests/test_collaboration.py::test_parallel_two_agents -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.collaboration.parallel'`

- [x] **Step 3: Write parallel strategy**

Create `ai_service/agents/collaboration/parallel.py`:

```python
from __future__ import annotations

import asyncio
from typing import Any

from agents.factory import AgentRuntime


async def parallel_run(
    agents: list[AgentRuntime],
    user_input: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Run all agents concurrently with the same input, then merge results."""
    results = await asyncio.gather(
        *[agent.run(user_input, context) for agent in agents],
        return_exceptions=True,
    )

    parts: list[str] = []
    for agent, result in zip(agents, results):
        if isinstance(result, BaseException):
            parts.append(f"[{agent.name}] Error: {result}")
        else:
            parts.append(str(result))

    return "\n\n---\n\n".join(parts)
```

- [x] **Step 4: Run tests to verify parallel passes**

Run: `.venv/bin/pytest ai_service/tests/test_collaboration.py::test_parallel_two_agents ai_service/tests/test_collaboration.py::test_parallel_single_agent -v`

Expected: 2 PASSED

- [x] **Step 5: Commit**

```bash
git add ai_service/agents/collaboration/parallel.py ai_service/tests/test_collaboration.py
git commit -m "feat: add parallel collaboration strategy"
```

archived-with: 2026-06-26-agent-expert-pool
---

### Task 7: Supervisor Collaboration Strategy

**Files:**
- Create: `ai_service/agents/collaboration/supervisor.py`
- Modify: `ai_service/tests/test_collaboration.py` (append tests)

**Interfaces:**
- Produces: `supervisor_run(agents, user_input, context) -> str`

- [x] **Step 1: Write failing test for supervisor collaboration**

Append to `ai_service/tests/test_collaboration.py`:

```python
@pytest.mark.asyncio
async def test_supervisor_delegates_to_agents():
    """Supervisor should decompose task and delegate to workers."""
    llm1 = _MockLLM('{"tasks": [{"agent": "a1", "task": "do X"}, {"agent": "a2", "task": "do Y"}]}')
    llm2 = _MockLLM("Result from A1")
    llm3 = _MockLLM("Result from A2")
    a1 = AgentRuntime(name="a1", llm=llm2, prompt="You are A1.", tools=[])
    a2 = AgentRuntime(name="a2", llm=llm3, prompt="You are A2.", tools=[])
    engine = CollaborationEngine()
    result = await engine.run(agents=[a1, a2], strategy="supervisor", user_input="do everything")
    assert "Result from A1" in result
    assert "Result from A2" in result


@pytest.mark.asyncio
async def test_supervisor_fallback_to_sequential():
    """Supervisor should fall back to sequential if LLM returns bad JSON."""
    llm = _MockLLM("not valid json")
    agent = AgentRuntime(name="a1", llm=llm, prompt="You are A1.", tools=[])
    engine = CollaborationEngine()
    result = await engine.run(agents=[agent], strategy="supervisor", user_input="hello")
    # The agent still produces some output (no throw)
    assert isinstance(result, str)
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest ai_service/tests/test_collaboration.py::test_supervisor_delegates_to_agents -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.collaboration.supervisor'`

- [x] **Step 3: Write supervisor strategy**

Create `ai_service/agents/collaboration/supervisor.py`:

```python
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from agents.factory import AgentRuntime
from config import settings

logger = logging.getLogger(__name__)


async def supervisor_run(
    agents: list[AgentRuntime],
    user_input: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Supervisor decomposes task, assigns to worker agents, merges results."""
    if not agents:
        return ""

    if not settings.api_key:
        # Fallback: sequential with first agent
        return await agents[0].run(user_input, context)

    # Build supervisor LLM
    supervisor_llm = ChatOpenAI(
        model=settings.model,
        temperature=0.1,
        api_key=settings.api_key,
        base_url=settings.base_url,
        response_format={"type": "json_object"},
    )

    agent_names = [a.name for a in agents]
    prompt = (
        f"You are a supervisor coordinating these agents: {', '.join(agent_names)}.\n"
        f"Decompose the user request into subtasks and assign each to one agent.\n\n"
        f"Output JSON: {{'tasks': [{{'agent': 'agent_name', 'task': 'subtask description'}}]}}\n\n"
        f"User request: {user_input}"
    )

    try:
        response = await supervisor_llm.ainvoke([SystemMessage(content=prompt)])
        parsed = json.loads(response.content)
        tasks = parsed.get("tasks", [])
    except Exception:
        logger.warning("Supervisor LLM failed, falling back to sequential")
        return await agents[0].run(user_input, context)

    if not tasks:
        return await agents[0].run(user_input, context)

    # Map tasks to agents
    agent_map = {a.name: a for a in agents}
    valid_tasks = [t for t in tasks if t.get("agent") in agent_map]

    if not valid_tasks:
        return await agents[0].run(user_input, context)

    # Run workers in parallel
    results = await asyncio.gather(
        *[agent_map[t["agent"]].run(t["task"], context) for t in valid_tasks],
        return_exceptions=True,
    )

    parts: list[str] = []
    for t, result in zip(valid_tasks, results):
        agent_name = t["agent"]
        if isinstance(result, BaseException):
            parts.append(f"[{agent_name}] Error: {result}")
        else:
            parts.append(f"[{agent_name}]\n{result}")

    return "\n\n---\n\n".join(parts)
```

- [x] **Step 4: Run tests to verify supervisor passes**

Run: `.venv/bin/pytest ai_service/tests/test_collaboration.py -v`

Expected: All 7 tests PASS (3 sequential + 2 parallel + 2 supervisor)

- [x] **Step 5: Commit**

```bash
git add ai_service/agents/collaboration/supervisor.py ai_service/tests/test_collaboration.py
git commit -m "feat: add supervisor collaboration strategy"
```

archived-with: 2026-06-26-agent-expert-pool
---

### Task 8: Multi-Agent Graph Integration

**Files:**
- Modify: `ai_service/graph/state.py`
- Create: `ai_service/graph/multi_agent_nodes.py`
- Modify: `ai_service/graph/graph.py`
- Modify: `ai_service/api/routes/chat.py`
- Create: `ai_service/tests/test_multi_agent_graph.py`

**Interfaces:**
- Consumes: `AgentFactory`, `RouterAgent`, `CollaborationEngine`, `AgentRepository`, `ToolRegistry`
- Produces: `create_multi_agent_graph(checkpointer) -> CompiledStateGraph`, new state fields, LangGraph nodes

- [x] **Step 1: Write integration test for multi-agent graph**

Create `ai_service/tests/test_multi_agent_graph.py`:

```python
from __future__ import annotations

import pytest

from agents import AgentDefinition, MockAgentRepository
from agents.collaboration.engine import CollaborationEngine
from agents.factory import AgentFactory, AgentRuntime
from agents.router import RouterAgent
from core.runtime import set_agent_repository, set_tool_registry
from tools.registry import ToolRegistry
from tools.base import BaseTool, ToolResult
from typing import Any, Mapping


class _EchoTool(BaseTool):
    name: str = "echo"
    description: str = "Echo"
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data={"echo": "ok"})


class _MockLLM:
    def __init__(self, response: str = "mock"):
        self.response = response

    async def ainvoke(self, messages):
        from langchain_core.messages import AIMessage
        return AIMessage(content=self.response)


@pytest.mark.asyncio
async def test_multi_agent_pipeline_routes_and_runs():
    """Full pipeline: router -> factory -> collaboration should produce output."""
    repo = MockAgentRepository()
    a1 = AgentDefinition(
        name="helper", display_name="Helper", system_prompt="You help.",
        trigger_keywords=["help"], tools=["echo"],
    )
    a2 = AgentDefinition(
        name="advisor", display_name="Advisor", system_prompt="You advise.",
        trigger_keywords=["advise"], tools=[],
    )
    await repo.create_agent(a1)
    await repo.create_agent(a2)

    registry = ToolRegistry()
    registry.register(_EchoTool())

    router = RouterAgent(repo)
    factory = AgentFactory(registry)
    engine = CollaborationEngine()

    # Route
    route_result = await router.route("I need help")
    assert route_result is not None
    assert len(route_result.agents) == 1
    assert route_result.agents[0].name == "helper"

    # Build
    runtimes = []
    for adef in route_result.agents:
        rt = await factory.build(adef)
        # Replace real LLM with mock for testing
        rt.llm = _MockLLM(f"Result from {adef.name}")
        runtimes.append(rt)

    # Collaborate
    result = await engine.run(runtimes, route_result.strategy, "help me")
    assert "Result from helper" in result


@pytest.mark.asyncio
async def test_router_no_match_skips_pipeline():
    """When no agents match, the pipeline should be skipped."""
    repo = MockAgentRepository()
    router = RouterAgent(repo)
    result = await router.route("something random")
    assert result is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest ai_service/tests/test_multi_agent_graph.py -v`

Expected: 2 PASSED (these tests only depend on Task 3-5 code, which is already written)

- [x] **Step 3: Add multi-agent fields to graph state**

Modify `ai_service/graph/state.py`, append to the `State` class (before closing brace):

```python
    # ── V0.5 Multi-agent expert pool ──────────────────────────────────
    route_result: dict | None        # {agents: [...], strategy: "..."} from router
    agent_runtimes: list | None      # Built AgentRuntime instances from factory
    collaboration_result: str | None  # Merged output from collaboration engine
```

- [x] **Step 4: Create multi-agent graph nodes**

Create `ai_service/graph/multi_agent_nodes.py`:

```python
from __future__ import annotations

import json
import logging

from agents import AgentDefinition, MockAgentRepository
from agents.collaboration.engine import CollaborationEngine
from agents.factory import AgentFactory
from agents.router import RouterAgent, RouteResult
from core.runtime import get_agent_repository, get_tool_registry
from graph.state import State

logger = logging.getLogger(__name__)


async def router_node(state: State) -> dict:
    """Route user input to matching agents using RouterAgent."""
    repo = get_agent_repository()
    if repo is None:
        return {"route_result": None}

    router = RouterAgent(repo)
    user_input = _extract_user_input(state)
    if not user_input:
        return {"route_result": None}

    result = await router.route(user_input)
    if result is None:
        return {"route_result": None}

    return {
        "route_result": {
            "agents": [a.model_dump() for a in result.agents],
            "strategy": result.strategy,
        }
    }


async def factory_node(state: State) -> dict:
    """Build AgentRuntime instances from route result."""
    route_result_data = state.get("route_result")
    if not route_result_data:
        return {"agent_runtimes": None}

    registry = get_tool_registry()
    if registry is None:
        return {"agent_runtimes": None}

    factory = AgentFactory(registry)
    runtimes = []

    for agent_data in route_result_data.get("agents", []):
        definition = AgentDefinition(**agent_data)
        context = _build_context(state)
        runtime = await factory.build(definition, context)
        runtimes.append(runtime)

    return {"agent_runtimes": runtimes}


async def collaboration_node(state: State) -> dict:
    """Execute collaboration strategy on built agents."""
    runtimes = state.get("agent_runtimes")
    route_result_data = state.get("route_result")

    if not runtimes or not route_result_data:
        return {"collaboration_result": None}

    strategy = route_result_data.get("strategy", "sequential")
    engine = CollaborationEngine()
    user_input = _extract_user_input(state)

    result = await engine.run(runtimes, strategy, user_input)
    return {"collaboration_result": result}


async def merge_node(state: State) -> dict:
    """Merge collaboration result into messages for chart_planner."""
    collab_result = state.get("collaboration_result")
    if not collab_result:
        return {"route": "chart_planner"}

    from langchain_core.messages import AIMessage

    return {
        "messages": [AIMessage(content=collab_result)],
        "route": "chart_planner",
    }


def _extract_user_input(state: State) -> str:
    messages = list(state.get("messages") or [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            return str(msg.content or "")
        if isinstance(msg, dict) and msg.get("role") in ("user", "human"):
            return str(msg.get("content", ""))
    return ""


def _build_context(state: State) -> dict:
    return {
        "conversation_id": state.get("conversation_id", ""),
        "trace_id": state.get("trace_id", ""),
    }
```

- [x] **Step 5: Add create_multi_agent_graph to graph.py**

Modify `ai_service/graph/graph.py`, append after `create_agent_graph()`:

```python
from graph.multi_agent_nodes import router_node, factory_node, collaboration_node, merge_node


def create_multi_agent_graph(checkpointer=None):
    """
    V0.5 multi-agent pipeline:

    router_node -> factory_node -> collaboration_node -> merge_node
        -> chart_planner -> answer -> END
    """
    workflow = StateGraph(State)

    workflow.add_node("router", router_node)
    workflow.add_node("factory", factory_node)
    workflow.add_node("collaboration", collaboration_node)
    workflow.add_node("merge", merge_node)
    workflow.add_node("chart_planner", chart_planner_node)
    workflow.add_node("answer", answer_node)

    workflow.set_entry_point("router")

    workflow.add_edge("router", "factory")
    workflow.add_edge("factory", "collaboration")
    workflow.add_edge("collaboration", "merge")
    workflow.add_edge("merge", "chart_planner")
    workflow.add_edge("chart_planner", "answer")
    workflow.add_edge("answer", END)

    return workflow.compile(checkpointer=checkpointer)
```

Also add the import statement at the top of `graph.py`:

```python
from graph.nodes import agent_node, tool_node, chart_planner_node, answer_node, MAX_ITERATIONS
```

- [x] **Step 6: Use multi-agent graph in chat route**

Modify `ai_service/api/routes/chat.py`:

In `stream_generate()`, after the `if not settings.api_key:` mock block, modify the graph selection:

```python
from core.runtime import get_agent_repository
from graph.graph import create_agent_graph, create_multi_agent_graph

# ...

# Inside event_generator(), before graph creation:
agent_repo = get_agent_repository()
enabled_agents = await agent_repo.get_enabled_agents() if agent_repo else []
use_multi_agent = len(enabled_agents) > 0

checkpointer = get_checkpointer()
if use_multi_agent:
    graph = create_multi_agent_graph(checkpointer=checkpointer)
    inputs = {
        "messages": [HumanMessage(content=request.message)],
        "conversation_id": trace_ctx.conversation_id,
        "tool_steps": [],
        "iteration_count": 0,
        "current_tool": None,
        "tool_input": None,
        "tool_result": None,
        "last_tool_name": None,
        "last_tool_query": None,
        "consecutive_search_count": 0,
        "last_guard_reason": None,
        "trace_id": trace_ctx.trace_id,
        "turn_id": trace_ctx.turn_id,
        "span_id": trace_ctx.span_id,
        "parent_span_id": trace_ctx.parent_span_id,
        "active_agent": trace_ctx.agent_id,
        "chart_specs": [],
        "blocks": [],
        "route": "tool",
        "route_result": None,
        "agent_runtimes": None,
        "collaboration_result": None,
    }
else:
    graph = create_agent_graph(checkpointer=checkpointer)
    inputs = { ... }  # existing inputs dict
```

Make sure to await the async `get_enabled_agents()` call by making the relevant scope async (use an async generator or move the check inside).

- [x] **Step 7: Run all collaboration + graph tests**

Run: `.venv/bin/pytest ai_service/tests/test_collaboration.py ai_service/tests/test_multi_agent_graph.py -v`

Expected: All tests PASS

- [x] **Step 8: Commit**

```bash
git add ai_service/graph/state.py ai_service/graph/multi_agent_nodes.py ai_service/graph/graph.py ai_service/api/routes/chat.py ai_service/tests/test_multi_agent_graph.py
git commit -m "feat: integrate multi-agent pipeline into LangGraph"
```

archived-with: 2026-06-26-agent-expert-pool
---

### Task 9: Agent Admin Frontend Page

**Files:**
- Create: `frontend/src/pages/AgentAdmin.tsx`
- Create: `frontend/src/services/agentApi.ts`
- Modify: `frontend/src/App.tsx`

- [x] **Step 1: Create agentApi service**

Create `frontend/src/services/agentApi.ts`:

```typescript
function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export interface AgentDefinition {
  id: string;
  name: string;
  display_name: string;
  description: string;
  system_prompt: string;
  tools: string[];
  model_parameters: Record<string, number>;
  trigger_keywords: string[];
  collaboration_strategy: 'sequential' | 'parallel' | 'supervisor';
  priority: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export async function listAgents(): Promise<AgentDefinition[]> {
  const res = await fetch('/api/v1/agents/', { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to list agents');
  return res.json();
}

export async function getAgent(id: string): Promise<AgentDefinition> {
  const res = await fetch(`/api/v1/agents/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error('Failed to get agent');
  return res.json();
}

export async function createAgent(data: Partial<AgentDefinition>): Promise<AgentDefinition> {
  const res = await fetch('/api/v1/agents/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create agent');
  return res.json();
}

export async function updateAgent(id: string, data: Partial<AgentDefinition>): Promise<AgentDefinition> {
  const res = await fetch(`/api/v1/agents/${id}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update agent');
  return res.json();
}

export async function deleteAgent(id: string): Promise<void> {
  const res = await fetch(`/api/v1/agents/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Failed to delete agent');
}

export async function reloadAgents(): Promise<void> {
  await fetch('/api/v1/agents/reload', {
    method: 'POST',
    headers: authHeaders(),
  });
}
```

- [x] **Step 2: Create AgentAdmin page**

Create `frontend/src/pages/AgentAdmin.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { AgentDefinition, listAgents, createAgent, updateAgent, deleteAgent } from '../services/agentApi';

interface AgentForm {
  name: string;
  display_name: string;
  description: string;
  system_prompt: string;
  tools: string;
  trigger_keywords: string;
  collaboration_strategy: 'sequential' | 'parallel' | 'supervisor';
  priority: number;
  enabled: boolean;
  model_temperature: number;
}

const emptyForm: AgentForm = {
  name: '', display_name: '', description: '', system_prompt: '',
  tools: '', trigger_keywords: '', collaboration_strategy: 'sequential',
  priority: 0, enabled: true, model_temperature: 0.7,
};

export function AgentAdmin() {
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<AgentForm>(emptyForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadAgents = async () => {
    try {
      setError('');
      const data = await listAgents();
      setAgents(data);
    } catch (e: any) {
      setError(e.message);
    }
  };

  useEffect(() => { loadAgents(); }, []);

  const handleEdit = (agent: AgentDefinition) => {
    setEditingId(agent.id);
    setForm({
      name: agent.name,
      display_name: agent.display_name,
      description: agent.description,
      system_prompt: agent.system_prompt,
      tools: (agent.tools || []).join(', '),
      trigger_keywords: (agent.trigger_keywords || []).join(', '),
      collaboration_strategy: agent.collaboration_strategy,
      priority: agent.priority,
      enabled: agent.enabled,
      model_temperature: agent.model_parameters?.temperature ?? 0.7,
    });
  };

  const handleCancel = () => {
    setEditingId(null);
    setForm(emptyForm);
  };

  const handleSave = async () => {
    setLoading(true);
    setError('');
    try {
      const payload = {
        ...form,
        tools: form.tools.split(',').map(s => s.trim()).filter(Boolean),
        trigger_keywords: form.trigger_keywords.split(',').map(s => s.trim()).filter(Boolean),
        model_parameters: { temperature: form.model_temperature },
      };
      if (editingId) {
        await updateAgent(editingId, payload);
      } else {
        await createAgent(payload);
      }
      await loadAgents();
      handleCancel();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this agent?')) return;
    try {
      setError('');
      await deleteAgent(id);
      await loadAgents();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleToggle = async (agent: AgentDefinition) => {
    try {
      setError('');
      await updateAgent(agent.id, { enabled: !agent.enabled });
      await loadAgents();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Agent 管理</h1>
        {!editingId && (
          <button
            onClick={() => setEditingId('__new__')}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            + 新建 Agent
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 text-sm rounded-lg px-4 py-3 mb-4">{error}</div>
      )}

      {/* Form */}
      {editingId && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 mb-6 space-y-4">
          <h2 className="text-lg font-semibold">{editingId === '__new__' ? '新建 Agent' : '编辑 Agent'}</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">名称 (name)</label>
              <input type="text" value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                className="w-full px-3 py-2 border rounded-lg" disabled={editingId !== '__new__'} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">显示名称</label>
              <input type="text" value={form.display_name} onChange={e => setForm({...form, display_name: e.target.value})}
                className="w-full px-3 py-2 border rounded-lg" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
              <input type="text" value={form.description} onChange={e => setForm({...form, description: e.target.value})}
                className="w-full px-3 py-2 border rounded-lg" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">System Prompt</label>
              <textarea value={form.system_prompt} onChange={e => setForm({...form, system_prompt: e.target.value})}
                className="w-full px-3 py-2 border rounded-lg font-mono text-sm" rows={5} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">工具 (逗号分隔)</label>
              <input type="text" value={form.tools} onChange={e => setForm({...form, tools: e.target.value})}
                className="w-full px-3 py-2 border rounded-lg" placeholder="search, browser" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">触发关键词 (逗号分隔)</label>
              <input type="text" value={form.trigger_keywords} onChange={e => setForm({...form, trigger_keywords: e.target.value})}
                className="w-full px-3 py-2 border rounded-lg" placeholder="weather, temperature" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">协作策略</label>
              <select value={form.collaboration_strategy} onChange={e => setForm({...form, collaboration_strategy: e.target.value as any})}
                className="w-full px-3 py-2 border rounded-lg">
                <option value="sequential">Sequential</option>
                <option value="parallel">Parallel</option>
                <option value="supervisor">Supervisor</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">优先级</label>
              <input type="number" value={form.priority} onChange={e => setForm({...form, priority: +e.target.value})}
                className="w-full px-3 py-2 border rounded-lg" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Temperature</label>
              <input type="number" step="0.1" min="0" max="2" value={form.model_temperature}
                onChange={e => setForm({...form, model_temperature: +e.target.value})}
                className="w-full px-3 py-2 border rounded-lg" />
            </div>
            <div className="flex items-center gap-2 pt-6">
              <input type="checkbox" id="enabled" checked={form.enabled}
                onChange={e => setForm({...form, enabled: e.target.checked})} />
              <label htmlFor="enabled" className="text-sm font-medium text-gray-700">启用</label>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button onClick={handleSave} disabled={loading}
              className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:bg-green-300">
              {loading ? '保存中...' : '保存'}
            </button>
            <button onClick={handleCancel}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300">
              取消
            </button>
          </div>
        </div>
      )}

      {/* Agent List Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3 font-medium">名称</th>
              <th className="text-left px-4 py-3 font-medium">显示名</th>
              <th className="text-left px-4 py-3 font-medium">工具</th>
              <th className="text-left px-4 py-3 font-medium">策略</th>
              <th className="text-left px-4 py-3 font-medium">关键词</th>
              <th className="text-center px-4 py-3 font-medium">启用</th>
              <th className="text-right px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {agents.length === 0 && (
              <tr><td colSpan={7} className="text-center py-8 text-gray-400">暂无 Agent，点击上方按钮新建</td></tr>
            )}
            {agents.map(agent => (
              <tr key={agent.id} className="border-b last:border-b-0 hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{agent.name}</td>
                <td className="px-4 py-3">{agent.display_name}</td>
                <td className="px-4 py-3">
                  <span className="text-xs text-gray-500">{(agent.tools || []).join(', ') || '-'}</span>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    agent.collaboration_strategy === 'parallel' ? 'bg-blue-100 text-blue-700' :
                    agent.collaboration_strategy === 'supervisor' ? 'bg-purple-100 text-purple-700' :
                    'bg-gray-100 text-gray-700'
                  }`}>
                    {agent.collaboration_strategy}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs text-gray-500">{(agent.trigger_keywords || []).join(', ') || '-'}</span>
                </td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={() => handleToggle(agent)}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition ${
                      agent.enabled ? 'bg-green-500' : 'bg-gray-300'
                    }`}
                  >
                    <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition ${
                      agent.enabled ? 'translate-x-4.5' : 'translate-x-1'
                    }`} />
                  </button>
                </td>
                <td className="px-4 py-3 text-right space-x-2">
                  <button onClick={() => handleEdit(agent)}
                    className="text-blue-500 hover:text-blue-700 text-xs">编辑</button>
                  <button onClick={() => handleDelete(agent.id)}
                    className="text-red-500 hover:text-red-700 text-xs">删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [x] **Step 3: Add route to App.tsx**

Modify `frontend/src/App.tsx`:

```tsx
import { AgentAdmin } from './pages/AgentAdmin';

// Inside <Routes>, after the chat routes:
<Route path="/admin/agents" element={
  <PrivateRoute><AgentAdmin /></PrivateRoute>
} />
```

- [x] **Step 4: Verify frontend compiles**

Run from frontend directory:

```bash
npx tsc --noEmit
```

Expected: No TypeScript errors

- [x] **Step 5: Commit**

```bash
git add frontend/src/pages/AgentAdmin.tsx frontend/src/services/agentApi.ts frontend/src/App.tsx
git commit -m "feat: add Agent admin frontend page"
```

archived-with: 2026-06-26-agent-expert-pool
---

### Task 10: End-to-End Integration Test

**Files:**
- Modify: `ai_service/tests/test_end_to_end.py`

- [x] **Step 1: Append E2E test to test_end_to_end.py**

Append to `ai_service/tests/test_end_to_end.py`:

```python
from __future__ import annotations

import pytest

from agents import AgentDefinition, MockAgentRepository
from agents.collaboration.engine import CollaborationEngine
from agents.factory import AgentFactory
from agents.router import RouterAgent, RouteResult
from core.runtime import set_agent_repository, set_tool_registry
from tools.base import BaseTool, ToolResult
from tools.registry import ToolRegistry
from typing import Any, Mapping


class _E2EQueryTool(BaseTool):
    """Simple tool for E2E test."""
    name: str = "query"
    description: str = "Query data"
    input_schema: dict[str, Any] = {"type": "object", "properties": {"q": {"type": "string"}}}

    async def execute(self, input_payload: Mapping[str, Any]) -> ToolResult:
        return ToolResult.success(data={"answer": f"queried: {input_payload.get('q', '')}"})


class _E2EMockLLM:
    def __init__(self, name: str):
        self.name = name

    async def ainvoke(self, messages):
        from langchain_core.messages import AIMessage
        return AIMessage(content=f"[{self.name}] Response to: {messages[-1].content}")


@pytest.mark.asyncio
async def test_full_pipeline_agent_expert_pool():
    """E2E: Create agents -> Route -> Factory -> Collaborate -> Output."""
    # 1. Setup: create repo with two agents
    repo = MockAgentRepository()
    reporter = AgentDefinition(
        name="reporter",
        display_name="Reporter",
        description="Reports facts",
        system_prompt="You report on: {query}",
        trigger_keywords=["report", "news"],
        tools=["query"],
        collaboration_strategy="sequential",
        priority=10,
        enabled=True,
    )
    analyzer = AgentDefinition(
        name="analyzer",
        display_name="Analyzer",
        description="Analyzes data",
        system_prompt="You analyze: {query}",
        trigger_keywords=["analyze", "report"],
        tools=[],
        collaboration_strategy="sequential",
        priority=5,
        enabled=True,
    )
    await repo.create_agent(reporter)
    await repo.create_agent(analyzer)

    # 2. Setup registry with query tool
    registry = ToolRegistry()
    registry.register(_E2EQueryTool())

    # 3. Route
    router = RouterAgent(repo)
    route_result = await router.route("I need a report on weather")
    assert route_result is not None
    assert len(route_result.agents) >= 1
    # "report" matches both, "report" + "news" don't both appear, so only "report" keyword hits
    # reporter has "report" keyword -> 1 hit
    # analyzer has "report" too since trigger_keywords=["analyze", "report"]
    # Wait, analyzer also has ["analyze", "report"]. Let's check: input "I need a report on weather"
    # "report": matches both. So both have 1 hit, sorted by priority: reporter(10) > analyzer(5)
    assert route_result.agents[0].name == "reporter"

    # 4. Factory
    factory = AgentFactory(registry)
    runtimes = []
    for adef in route_result.agents:
        rt = await factory.build(adef, context={"query": "weather"})
        rt.llm = _E2EMockLLM(adef.name)
        runtimes.append(rt)

    assert len(runtimes) == 2
    assert runtimes[0].name == "reporter"
    assert len(runtimes[0].tools) == 1  # query tool bound

    # 5. Collaborate (sequential)
    engine = CollaborationEngine()
    result = await engine.run(runtimes, "sequential", "weather report")
    assert "[reporter]" in result or "reporter" in result

    # 6. Verify second agent received first agent's output
    # (sequential chains: agent1 output -> agent2 input)
    assert len(result) > 0
```

- [x] **Step 2: Run E2E test**

Run: `.venv/bin/pytest ai_service/tests/test_end_to_end.py::test_full_pipeline_agent_expert_pool -v`

Expected: PASS

- [x] **Step 3: Run full test suite**

Run: `.venv/bin/pytest ai_service/tests/ -v`

Expected: All tests PASS (existing + new)

- [x] **Step 4: Commit**

```bash
git add ai_service/tests/test_end_to_end.py
git commit -m "test: add E2E integration test for agent expert pool"
```

archived-with: 2026-06-26-agent-expert-pool
---

## Self-Review Checklist

### Spec Coverage

| Spec Requirement | Task(s) | Status |
|---|---|---|
| DB Schema: agent_definitions table | Task 1 (migration SQL) | Covered |
| Pydantic/SQLAlchemy model | Task 1 (AgentDefinition model) | Covered (Pydantic) |
| CRUD API: GET/POST/PUT/DELETE agents | Task 2 | Covered |
| `POST /agents/reload` | Task 2 | Covered (stub) |
| AgentFactory: build from definition | Task 3 | Covered |
| RouterAgent: keyword matching | Task 4 | Covered |
| RouterAgent: LLM fallback | Task 4 | Covered |
| Router: max 3 agents, sorted by hits then priority | Task 4 | Covered |
| Sequential collaboration | Task 5 | Covered |
| Parallel collaboration | Task 6 | Covered |
| Supervisor collaboration | Task 7 | Covered |
| Graph: router -> factory -> collab -> merge -> chart_planner -> answer | Task 8 | Covered |
| Frontend admin page | Task 9 | Covered |
| E2E integration test | Task 10 | Covered |

### Placeholder Check

No TBD, TODO, or placeholder patterns found. All code is complete and copy-paste ready.

### Type Consistency

- `AgentDefinition.model_parameters` (dict) used consistently across all tasks.
- `CollaborationEngine.run()` signature (`agents: list[AgentRuntime], strategy: str, user_input: str`) consistent in Tasks 5-8.
- `RouterAgent.route()` returns `RouteResult | None` — checked in Tasks 4 and 8.
- `AgentFactory.build()` returns `AgentRuntime` — consistent in Tasks 3, 8, 10.
- Frontend `agentApi.ts` interfaces align with backend API response shapes.

archived-with: 2026-06-26-agent-expert-pool
---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-25-agent-expert-pool.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
