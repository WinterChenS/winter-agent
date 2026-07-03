from context.models import ContextFragment


def render_context_prompt(
    fragments: list[ContextFragment],
) -> tuple[str, dict[str, list[str] | list[dict[str, str]]]]:
    if not fragments:
        return "", {"providers": [], "recent_messages": []}

    blocks = [f"[{fragment.provider}]\n{fragment.content}" for fragment in fragments]
    recent_messages = next(
        (
            fragment.metadata.get("recent_messages", [])
            for fragment in fragments
            if fragment.provider == "session"
        ),
        [],
    )
    metadata = {
        "providers": [fragment.provider for fragment in fragments],
        "recent_messages": recent_messages,
    }
    return "\n\n".join(blocks), metadata