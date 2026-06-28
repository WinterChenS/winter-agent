from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from models.agent import AgentDefinition
from core.runtime import get_agent_repository

# Authentication is handled upstream by the Spring Boot BFF (JWT gateway).
# The AI service (FastAPI) does not manage auth itself.
router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("/")
async def list_agents() -> list[AgentDefinition]:
    repo = get_agent_repository()
    return await repo.list_all()


@router.post("/")
async def create_agent(agent: AgentDefinition, x_user: str = Header(default="")) -> AgentDefinition:
    repo = get_agent_repository()
    agent.created_by = x_user
    return await repo.create(agent)


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> AgentDefinition:
    repo = get_agent_repository()
    result = await repo.get_by_id(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@router.put("/{agent_id}")
async def update_agent(agent_id: str, agent: AgentDefinition, x_user: str = Header(default="")) -> AgentDefinition:
    repo = get_agent_repository()
    agent.updated_by = x_user
    result = await repo.update(agent_id, agent)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str) -> dict[str, str]:
    repo = get_agent_repository()
    ok = await repo.delete(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "deleted"}


@router.post("/{agent_id}/enable")
async def enable_agent(agent_id: str, x_user: str = Header(default="")) -> AgentDefinition:
    repo = get_agent_repository()
    result = await repo.set_enabled(agent_id, True, updated_by=x_user)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@router.post("/{agent_id}/disable")
async def disable_agent(agent_id: str, x_user: str = Header(default="")) -> AgentDefinition:
    repo = get_agent_repository()
    result = await repo.set_enabled(agent_id, False, updated_by=x_user)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@router.post("/{agent_id}/clone")
async def clone_agent(agent_id: str, x_user: str = Header(default="")) -> AgentDefinition:
    repo = get_agent_repository()
    result = await repo.clone(agent_id, created_by=x_user)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result
