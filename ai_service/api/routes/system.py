from fastapi import APIRouter

from config import settings
from decorator.log import log

router = APIRouter(tags=["system"])


@router.get("/health")
@log
async def health_check():
    api_key = settings.api_key
    mode = "llm" if api_key else "mock"
    return {
        "status": "healthy",
        "mode": mode,
        "model": settings.model if api_key else None,
    }


@router.get("/")
async def root():
    return {
        "message": "AI Chat Service V0.2",
        "endpoints": ["/health", "/api/v1/generate/stream", "/api/v1/history/{conversation_id}"],
    }

