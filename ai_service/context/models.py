from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ContextRequest:
    session_id: str | None
    user_query: str
    agent_id: str | None
    max_tokens: int


@dataclass(slots=True)
class ContextFragment:
    provider: str
    content: str
    tokens: int
    priority: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentContext:
    session_id: str | None
    agent_id: str | None
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    fragments: list[ContextFragment] = field(default_factory=list)
    rendered_prompt: str = ""
    token_usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)