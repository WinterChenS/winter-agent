from __future__ import annotations

import json
from urllib.parse import urlparse


def normalize_tool_result_for_prompt(tool_result: str | None) -> str:
    """Build a safe compact context block from raw tool output."""
    if not tool_result:
        return ""

    try:
        parsed = json.loads(tool_result)
    except Exception:
        return "Tool returned data (sanitized)."

    if not isinstance(parsed, dict):
        return "Tool returned structured data (sanitized)."

    ok = bool(parsed.get("ok", False))
    if not ok:
        err = str(parsed.get("error") or parsed.get("message") or "unknown error")[:200]
        return f"Tool execution failed: {err}"

    data = parsed.get("data")

    if isinstance(data, str):
        compact = " ".join(data.split())[:120]
        return f"time: {compact}" if compact else "time: (available)"

    data = data if isinstance(data, dict) else {}
    query = str(data.get("query") or "").strip()
    results = data.get("results") if isinstance(data.get("results"), list) else []

    lines: list[str] = []
    if query:
        lines.append(f"query: {query[:120]}")
    lines.append(f"result_count: {len(results)}")

    for idx, item in enumerate(results[:3], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()[:120]
        url = str(item.get("url") or "").strip()
        domain = ""
        if url:
            try:
                domain = urlparse(url).netloc[:80]
            except Exception:
                domain = ""
        if title or domain:
            lines.append(f"{idx}. title={title or '-'}; source={domain or '-'}")

    return "\n".join(lines) if lines else "Tool returned structured data (sanitized)."


def normalize_tool_step_record(
    tool_name: str,
    tool_input: dict | str | None,
    status: str,
    elapsed_ms: int,
    timestamp: float,
    error: str | None = None,
) -> dict:
    query = ""
    if isinstance(tool_input, dict):
        query = str(tool_input.get("query", ""))
    elif tool_input is not None:
        query = str(tool_input)

    record = {
        "tool": tool_name,
        "input": query,
        "status": status,
        "elapsed_ms": max(0, int(elapsed_ms)),
        "timestamp": timestamp,
    }
    if status == "error" and error:
        record["error"] = error
    return record

