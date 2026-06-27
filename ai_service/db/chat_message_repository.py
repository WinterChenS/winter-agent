from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from psycopg_pool import AsyncConnectionPool


def _parse_tool_calls(value: Any) -> list[dict[str, Any]] | None:
    """Parse tool_calls from DB row. psycopg auto-deserializes JSONB to list,
    but legacy rows may have plain JSON strings or NULL."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


async def save_message(pool: AsyncConnectionPool, message: dict[str, Any]) -> None:
    """Async insert a completed message into chat_messages table."""
    sql = """
        INSERT INTO chat_messages (id, conversation_id, role, content,
            reasoning, tool_calls, status, agent_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            content = EXCLUDED.content,
            reasoning = EXCLUDED.reasoning,
            tool_calls = EXCLUDED.tool_calls,
            status = EXCLUDED.status
    """
    async with pool.connection() as conn:
        await conn.execute(sql, (
            message["id"],
            message.get("conversation_id"),
            message["role"],
            message.get("content", ""),
            message.get("reasoning"),
            json.dumps(message.get("toolCalls", [])) if message.get("toolCalls") else None,
            message.get("status", "done"),
            message.get("agentId"),
            datetime.fromtimestamp(
                message.get("createdAt", 0) / 1000, tz=timezone.utc
            ) if message.get("createdAt") else datetime.now(timezone.utc),
        ))


async def get_messages_by_conversation(
    pool: AsyncConnectionPool, conversation_id: str
) -> list[dict[str, Any]]:
    """Load message history for a conversation."""
    sql = """
        SELECT id, conversation_id, role, content, reasoning,
               tool_calls, status, agent_id,
               EXTRACT(EPOCH FROM created_at)::bigint * 1000 AS created_at
        FROM chat_messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC
    """
    async with pool.connection() as conn:
        rows = await conn.execute(sql, (conversation_id,))
        records = await rows.fetchall()

    messages = []
    for row in records:
        msg = {
            "id": row[0],
            "conversationId": row[1],
            "role": row[2],
            "content": row[3],
            "reasoning": row[4],
            "toolCalls": _parse_tool_calls(row[5]),
            "status": row[6],
            "agentId": row[7],
            "createdAt": int(row[8]) if row[8] else None,
        }
        messages.append(msg)
    return messages
