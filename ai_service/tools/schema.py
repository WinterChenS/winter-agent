from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ToolSchema(BaseModel):
    """OpenAI function-calling schema for a tool's input parameters."""

    parameters: dict[str, Any]


def tool(cls):
    """Decorator that marks a class as a discoverable tool.

    Sets ``cls._is_tool = True`` on the decorated class and returns it
    unchanged.
    """
    cls._is_tool = True
    return cls
