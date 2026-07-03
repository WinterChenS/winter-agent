def estimate_text_tokens(text: str) -> int:
    return len([part for part in text.split() if part.strip()])


def trim_text_to_budget(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""

    parts = [part for part in text.split() if part.strip()]
    return " ".join(parts[:max_tokens])