from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.agents import router
from core.runtime import set_agent_repository
from models.agent import AgentDefinition
from repositories.agent_repository import AgentRepository, MockAgentRepository


@pytest.fixture
def repo() -> AgentRepository:
    return MockAgentRepository()


@pytest.fixture
def sample_agent() -> AgentDefinition:
    return AgentDefinition(
        name="test", display_name="Test", system_prompt="Be helpful.",
        tools=["search"], trigger_keywords=["搜索"], collaboration_strategy="parallel",
    )


@pytest.mark.asyncio
async def test_create_and_list(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    assert created.name == "test"
    agents = await repo.list_all()
    assert len(agents) == 1


@pytest.mark.asyncio
async def test_get_by_id(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.name == "test"


@pytest.mark.asyncio
async def test_update(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    updated_agent = AgentDefinition(name="updated", display_name="Updated", system_prompt="New")
    result = await repo.update(created.id, updated_agent)
    assert result is not None
    assert result.name == "updated"


@pytest.mark.asyncio
async def test_delete(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    ok = await repo.delete(created.id)
    assert ok is True
    assert await repo.get_by_id(created.id) is None


@pytest.mark.asyncio
async def test_list_enabled(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    await repo.create(sample_agent)
    disabled = AgentDefinition(name="off", display_name="Off", system_prompt="...", enabled=False)
    await repo.create(disabled)
    agents = await repo.list_enabled()
    assert len(agents) == 1
    assert agents[0].name == "test"


@pytest.mark.asyncio
async def test_update_nonexistent_returns_none(repo: AgentRepository) -> None:
    agent = AgentDefinition(name="ghost", display_name="Ghost", system_prompt="...")
    result = await repo.update("nonexistent", agent)
    assert result is None


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_false(repo: AgentRepository) -> None:
    ok = await repo.delete("nonexistent")
    assert ok is False


@pytest.mark.asyncio
async def test_get_by_id_nonexistent_returns_none(repo: AgentRepository) -> None:
    found = await repo.get_by_id("nonexistent")
    assert found is None


# ── API endpoint tests (enable/disable/clone + X-User header) ──────────────


@pytest.fixture
def client():
    """Create a TestClient with a fresh MockAgentRepository set as global."""
    repo = MockAgentRepository()
    set_agent_repository(repo)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestXUserHeader:
    """X-User header handling on create and update endpoints."""

    def test_create_agent_sets_created_by_from_x_user(self, client):
        payload = {
            "name": "xuser-create",
            "display_name": "XUser Create",
            "system_prompt": "Be helpful.",
        }
        resp = client.post("/api/v1/agents/", json=payload, headers={"X-User": "alice"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["created_by"] == "alice"

    def test_create_agent_x_user_fallback_empty_string(self, client):
        payload = {
            "name": "no-xuser",
            "display_name": "No XUser",
            "system_prompt": "Be helpful.",
        }
        resp = client.post("/api/v1/agents/", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created_by"] == ""

    def test_update_agent_sets_updated_by_from_x_user(self, client):
        create_payload = {
            "name": "pre-update",
            "display_name": "Pre Update",
            "system_prompt": "Old prompt",
        }
        create_resp = client.post("/api/v1/agents/", json=create_payload)
        agent_id = create_resp.json()["id"]

        update_payload = {
            "name": "post-update",
            "display_name": "Post Update",
            "system_prompt": "New prompt",
        }
        resp = client.put(
            f"/api/v1/agents/{agent_id}",
            json=update_payload,
            headers={"X-User": "bob"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated_by"] == "bob"

    def test_update_agent_x_user_fallback_empty_string(self, client):
        create_payload = {
            "name": "pre-update-2",
            "display_name": "Pre Update 2",
            "system_prompt": "Old prompt",
        }
        create_resp = client.post("/api/v1/agents/", json=create_payload)
        agent_id = create_resp.json()["id"]

        update_payload = {
            "name": "post-update-2",
            "display_name": "Post Update 2",
            "system_prompt": "New prompt",
        }
        resp = client.put(f"/api/v1/agents/{agent_id}", json=update_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated_by"] == ""


class TestEnableDisableEndpoints:
    """Enable/disable endpoints."""

    def test_enable_agent(self, client):
        create_resp = client.post("/api/v1/agents/", json={
            "name": "enable-test",
            "display_name": "Enable Test",
            "system_prompt": "Test",
        })
        agent_id = create_resp.json()["id"]

        # First disable via API
        client.post(f"/api/v1/agents/{agent_id}/disable", headers={"X-User": "admin"})

        # Then enable
        resp = client.post(f"/api/v1/agents/{agent_id}/enable", headers={"X-User": "admin"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["updated_by"] == "admin"

    def test_enable_nonexistent_agent_returns_404(self, client):
        resp = client.post("/api/v1/agents/nonexistent/enable", headers={"X-User": "admin"})
        assert resp.status_code == 404

    def test_disable_agent(self, client):
        create_resp = client.post("/api/v1/agents/", json={
            "name": "disable-test",
            "display_name": "Disable Test",
            "system_prompt": "Test",
        })
        agent_id = create_resp.json()["id"]

        resp = client.post(f"/api/v1/agents/{agent_id}/disable", headers={"X-User": "admin"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["updated_by"] == "admin"

    def test_disable_nonexistent_agent_returns_404(self, client):
        resp = client.post("/api/v1/agents/nonexistent/disable", headers={"X-User": "admin"})
        assert resp.status_code == 404


class TestCloneEndpoint:
    """Clone endpoint."""

    def test_clone_agent_creates_copy(self, client):
        create_resp = client.post("/api/v1/agents/", json={
            "name": "clone-original",
            "display_name": "Clone Original",
            "system_prompt": "Be cloned.",
        })
        original = create_resp.json()
        original_id = original["id"]

        resp = client.post(f"/api/v1/agents/{original_id}/clone", headers={"X-User": "tester"})
        assert resp.status_code == 200
        cloned = resp.json()
        assert cloned["id"] != original_id
        assert cloned["display_name"] == "Clone Original (Copy)"
        assert cloned["created_by"] == "tester"

    def test_clone_nonexistent_agent_returns_404(self, client):
        resp = client.post("/api/v1/agents/nonexistent/clone", headers={"X-User": "tester"})
        assert resp.status_code == 404
