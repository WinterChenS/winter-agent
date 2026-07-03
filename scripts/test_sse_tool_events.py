"""Test SSE tool events and image flow."""
import asyncio
import json
import sys
from typing import Any

import httpx


URL = "http://127.0.0.1:8000/api/v1/generate/stream"
MSG = "搜索2024年中国GDP增速和CPI数据，用图表展示"


async def main() -> None:
    events: list[dict[str, Any]] = []
    type_counts: dict[str, int] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(120)) as client:
        async with client.stream("POST", URL, json={
            "message": MSG,
            "conversationId": f"test-{int(asyncio.get_event_loop().time())}",
        }) as resp:
            print(f"Status: {resp.status_code}")
            buf = b""
            async for chunk in resp.aiter_raw():
                buf += chunk

    # Parse SSE frames
    raw_text = buf.decode("utf-8", errors="replace")
    for frame in raw_text.split("\n\n"):
        for line in frame.split("\n"):
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if not data or data == "[DONE]":
                continue
            try:
                ev = json.loads(data)
            except json.JSONDecodeError:
                print(f"PARSE: {data[:80]}")
                continue
            events.append(ev)
            t = ev.get("type", "?")
            type_counts[t] = type_counts.get(t, 0) + 1

    # Report
    print(f"\nTotal events: {len(events)}")
    print("Type counts:")
    for t, c in sorted(type_counts.items()):
        marker = " <<<" if "tool" in t.lower() else ""
        print(f"  {t}: {c}{marker}")

    # Check expected
    for expected in ("tool.started", "tool.finished", "tool.failed"):
        if expected not in type_counts:
            print(f"\n[FAIL] {expected}: 0 events")

    image_events = [e for e in events if e.get("type") == "image.uploaded"]
    print(f"\nImage uploaded events: {len(image_events)}")

    if not any("tool" in t.lower() for t in type_counts):
        print("\n[FAIL] No tool events received. Dumping conversation.started:")
        for e in events:
            if e.get("type") == "conversation.started":
                print(json.dumps(e, ensure_ascii=False, indent=2)[:500])
                break


if __name__ == "__main__":
    asyncio.run(main())
