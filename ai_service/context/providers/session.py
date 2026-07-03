from __future__ import annotations

import logging
from typing import Any

from context.budget import estimate_text_tokens
from context.models import ContextFragment, ContextRequest
from db.chat_message_repository import get_messages_by_conversation

logger = logging.getLogger(__name__)


class SessionContextProvider:
    name = "session"
    priority = 10

    def __init__(self, pool: Any, history_limit: int = 10) -> None:
        self._pool = pool
        self._history_limit = history_limit

    async def collect(self, request: ContextRequest) -> list[ContextFragment]:
        if not request.session_id or not self._pool:
            return []

        try:
            messages = await get_messages_by_conversation(self._pool, request.session_id)
        except Exception as exc:
            logger.warning("session context provider failed: %s", exc)
            return []

        visible_messages = [
            message
            for message in (self._filter_message(item) for item in messages)
            if message is not None
        ]

        if self._history_limit <= 0:
            return []

        recent_messages = visible_messages[-self._history_limit :]
        if not recent_messages:
            return []

        content = "\n".join(
            f"{message['role']}: {message['content']}" for message in recent_messages
        )
        return [
            ContextFragment(
                provider=self.name,
                content=content,
                tokens=estimate_text_tokens(content),
                priority=self.priority,
                metadata={"recent_messages": recent_messages},
            )
        ]

    def _filter_message(self, message: dict[str, Any]) -> dict[str, str] | None:
        content = str(message.get("content") or "").strip()
        if not content or self._is_internal_message(content):
            return None

        return {
            "role": str(message.get("role") or "assistant"),
            "content": content,
        }

    def _is_internal_message(self, content: str) -> bool:
        stripped = content.strip()
        if stripped.startswith("Thought:"):
            return True
        if stripped.startswith("Action:"):
            return True
        if stripped.startswith("Observation:"):
            return True
        if stripped.startswith("[SYSTEM:") or stripped.startswith("[Tool result:"):
            return True
        if stripped.startswith("Observation (") and "):" in stripped[:30]:
            return True
        if stripped.startswith('{"action"'):
            return True
        if stripped.startswith('{"need_chart"'):
            return True
        return False