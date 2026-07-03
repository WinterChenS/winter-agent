from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from langchain_openai import ChatOpenAI

from config import settings
from core.runtime import get_tool_registry
from models.agent import AgentDefinition


@dataclass
class AgentRuntime:
    """A fully assembled agent ready to execute."""

    name: str
    display_name: str = ""
    llm: ChatOpenAI | None = None
    system_prompt: str = ""
    tools: list | None = None
    strategy: str = "sequential"

    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.name
        if self.tools is None:
            self.tools = []


class AgentFactory:
    def build(self, definition: AgentDefinition, context: dict | None = None) -> AgentRuntime:
        """Assemble an AgentRuntime from an AgentDefinition."""
        ctx = dict(context or {})
        ctx.setdefault("current_time", datetime.now().strftime("%Y-%m-%d %H:%M"))
        runtime_context_prompt = str(ctx.pop("runtime_context_prompt", "") or "").strip()

        # Render prompt template
        prompt = definition.system_prompt
        for key, value in ctx.items():
            prompt = prompt.replace("{" + key + "}", str(value))
        if runtime_context_prompt:
            prompt = f"{prompt}\n\nRuntime context:\n{runtime_context_prompt}"

        # Resolve tools
        registry = get_tool_registry()
        tools = []
        if registry:
            for tool_name in definition.tools:
                try:
                    tools.append(registry.get(tool_name))
                except Exception:
                    pass  # Skip unknown tools

        # Build LLM
        llm = ChatOpenAI(
            model=settings.model,
            temperature=definition.model_params.get("temperature", 0.7),
            streaming=False,
            api_key=settings.api_key,
            base_url=settings.base_url,
        )

        return AgentRuntime(
            name=definition.name,
            display_name=definition.display_name or definition.name,
            llm=llm,
            system_prompt=prompt,
            tools=tools,
            strategy=definition.collaboration_strategy,
        )
