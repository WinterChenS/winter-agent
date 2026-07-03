from context.budget import estimate_text_tokens, trim_text_to_budget
from context.models import ContextFragment


def assemble_fragments(
    fragments: list[ContextFragment], max_tokens: int
) -> tuple[list[ContextFragment], dict[str, int]]:
    ordered = sorted(fragments, key=lambda item: item.priority)
    kept: list[ContextFragment] = []
    token_usage: dict[str, int] = {}
    remaining = max_tokens

    for fragment in ordered:
        if remaining <= 0:
            break

        trimmed_content = trim_text_to_budget(fragment.content, remaining)
        if not trimmed_content:
            continue

        trimmed_tokens = min(estimate_text_tokens(trimmed_content), remaining)
        kept.append(
            ContextFragment(
                provider=fragment.provider,
                content=trimmed_content,
                tokens=trimmed_tokens,
                priority=fragment.priority,
                metadata=fragment.metadata,
            )
        )
        token_usage[fragment.provider] = (
            token_usage.get(fragment.provider, 0) + trimmed_tokens
        )
        remaining -= trimmed_tokens

    return kept, token_usage