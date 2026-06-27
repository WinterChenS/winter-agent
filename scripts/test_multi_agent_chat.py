#!/usr/bin/env python3
"""
Test script for the multi-agent chat endpoint.
Tests: SSE stream connectivity, router agent selection, collaboration execution.
Usage: python scripts/test_multi_agent_chat.py
"""
import asyncio
import json
import sys
import httpx

BASE_URL = "http://localhost:8000/api/v1"
TIMEOUT = 60.0


async def test_agent_list():
    """Test 1: List available agents."""
    print("\n" + "=" * 60)
    print("TEST 1: List Agents")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{BASE_URL}/agents/")
        print(f"  Status: {resp.status_code}")
        agents = resp.json()
        print(f"  Agent count: {len(agents)}")
        for a in agents if isinstance(agents, list) else agents.get("content", []):
            print(f"    - {a.get('id','?')}: {a.get('display_name','?')} "
                  f"tools={a.get('tools','?')} enabled={a.get('enabled','?')}")
        return agents if isinstance(agents, list) else []


async def test_chat_stream(message: str, agent_id: str | None = None):
    """Test 2: Send a chat message and stream SSE events."""
    print("\n" + "=" * 60)
    print(f"TEST 2: Chat Stream")
    print(f"  message: {message}")
    print(f"  agent_id: {agent_id}")
    print("=" * 60)

    event_types = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        body = {
            "message": message,
            "conversationId": None,
            "agentId": agent_id,
            "messageId": f"test-{id(message)}",
            "stream": True,
        }
        print(f"  Request body: {json.dumps(body, ensure_ascii=False)}")

        try:
            async with client.stream(
                "POST",
                f"{BASE_URL}/generate/stream",
                json=body,
                headers={"Content-Type": "application/json"},
            ) as resp:
                print(f"  Status: {resp.status_code}")
                print(f"  Headers: {dict(resp.headers)}")

                line_count = 0
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    line_count += 1

                    # Parse SSE data
                    if line.startswith("data: "):
                        data_str = line[6:]
                    elif line.startswith("data:"):
                        data_str = line[5:]
                    else:
                        print(f"  [line {line_count}] RAW: {line[:100]}")
                        continue

                    try:
                        event = json.loads(data_str)
                        etype = event.get("type", "unknown")
                        event_types.append(etype)

                        if etype in ("message.tool_call",):
                            tc = event.get("toolCall") or event.get("payload", {}).get("toolCall", {})
                            print(f"  [{line_count}] 🛠️ TOOL_CALL: {tc.get('name')} status={tc.get('status')}")
                        elif etype == "message.reasoning":
                            delta = event.get("delta", "")
                            print(f"  [{line_count}] 💭 REASONING: {delta[:100]}")
                        elif etype == "message.delta":
                            delta = event.get("delta", "")
                            print(f"  [{line_count}] 📝 DELTA: {delta[:100]}")
                        elif etype == "message.done":
                            print(f"  [{line_count}] ✅ DONE: status={event.get('status')}")
                        elif etype == "error":
                            print(f"  [{line_count}] ❌ ERROR: {event.get('error')}")
                        else:
                            payload_keys = list(event.get("payload", {}).keys()) if "payload" in event else []
                            print(f"  [{line_count}] {etype} keys={list(event.keys())[:8]} payload_keys={payload_keys}")

                        # Stop after done or error
                        if etype in ("message.done", "error"):
                            break

                    except json.JSONDecodeError:
                        print(f"  [{line_count}] JSON parse error: {data_str[:100]}")

                print(f"\n  Total lines received: {line_count}")
        except httpx.ConnectError:
            print(f"  ❌ Connection refused — is the AI service running on port 8000?")
            return None
        except Exception as e:
            print(f"  ❌ Stream error: {type(e).__name__}: {e}")
            return None

    # Summary
    print(f"\n  Event type summary:")
    from collections import Counter
    for etype, count in Counter(event_types).items():
        print(f"    {etype}: {count}")

    return event_types


async def main():
    print("Multi-Agent Chat Test Suite")
    print(f"Target: {BASE_URL}")

    # Test 1: List agents
    agents = await test_agent_list()

    if not agents:
        print("\n⚠️ No agents found. Make sure the database is seeded.")
        print("  Run: python scripts/run_migration.py")
        return

    # Test 2: General query (without specific agent)
    event_types = await test_chat_stream(
        "帮我搜索一下最近有什么科技大新闻",
        agent_id="srch-agent",
    )

    if event_types is None:
        print("\n❌ First test failed — aborting")
        return

    # Test 3: Simple query (no tools needed)
    await test_chat_stream(
        "你好，请简单介绍一下你自己",
        agent_id=None,
    )

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
