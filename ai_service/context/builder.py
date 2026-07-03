from context.assembler import assemble_fragments
from context.injector import render_context_prompt
from context.models import AgentContext, ContextRequest


class ContextBuilder:
    def __init__(self, providers) -> None:
        self._providers = providers

    async def build(self, request: ContextRequest) -> AgentContext:
        collected = []
        for provider in self._providers:
            try:
                collected.extend(await provider.collect(request))
            except Exception:
                continue

        fragments, token_usage = assemble_fragments(collected, request.max_tokens)
        rendered_prompt, metadata = render_context_prompt(fragments)

        return AgentContext(
            session_id=request.session_id,
            agent_id=request.agent_id,
            recent_messages=metadata.get("recent_messages", []),
            fragments=fragments,
            rendered_prompt=rendered_prompt,
            token_usage=token_usage,
            metadata=metadata,
        )