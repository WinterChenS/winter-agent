from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.agent import AgentDefinition
from core.runtime import get_agent_repository

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("/")
async def list_agents() -> list[AgentDefinition]:
    repo = get_agent_repository()
    return await repo.list_all()


@router.post("/")
async def create_agent(agent: AgentDefinition) -> AgentDefinition:
    repo = get_agent_repository()
    return await repo.create(agent)


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> AgentDefinition:
    repo = get_agent_repository()
    result = await repo.get_by_id(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result


@router.put("/{agent_id}")
async def update_agent(agent_id: str, agent: AgentDefinition) -> AgentDefinition:
    repo = get_agent_repository()
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
