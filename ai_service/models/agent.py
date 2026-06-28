from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

COLLABORATION_STRATEGIES = {"sequential", "parallel", "supervisor"}


class AgentDefinition(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    description: str = ""
    system_prompt: str
    tools: list[str] = []
    model_params: dict[str, Any] = Field(
        default_factory=lambda: {"temperature": 0.7},
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    trigger_keywords: list[str] = []
    collaboration_strategy: str = "sequential"
    priority: int = 0
    enabled: bool = True
    icon: str = ""
    agent_type: str = ""
    avatar_url: str = ""
    is_builtin: bool = False
    tags: list[str] = []
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str = ""
    updated_by: str = ""
    version: int = 1
    created_at: str = ""
    updated_at: str = ""

    @field_validator("collaboration_strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        if v not in COLLABORATION_STRATEGIES:
            raise ValueError(
                f"collaboration_strategy must be one of {COLLABORATION_STRATEGIES}, got '{v}'"
            )
        return v
