#!/usr/bin/env python3
"""LLM Chat Scenario Tests — verify the chat/generate/stream endpoint with different scenarios."""

import json
import sys
import urllib.request

BASE_URL = "http://localhost:8000/api/v1/generate/stream"


def stream_query(message: str, timeout: int = 60) -> dict:
    """Send a streaming query and collect event types + response text."""
    body = json.dumps({
        "message": message,
        "conversationId": f"test-{message[:10].replace(' ', '-')}",
    }).encode("utf-8")

    req = urllib.request.Request(BASE_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")

    events = {"message.delta": 0, "message.tool_call": 0, "message.reasoning": 0, "message.done": 0, "chart": 0, "error": 0}
    tokens = []
    message_ids = set()

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            buffer = ""
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8")

                # Parse SSE events
                while "\n\n" in buffer:
                    frame, buffer = buffer.split("\n\n", 1)
                    for line in frame.split("\n"):
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                continue
                            try:
                                event = json.loads(data_str)
                                etype = event.get("type", "unknown")
                                if etype in events:
                                    events[etype] += 1
                                if etype == "message.delta":
                                    content = event.get("delta") or ""
                                    tokens.append(content)
                                # Verify messageId is present for all non-error events
                                if etype != "error":
                                    assert "messageId" in event, f"Missing messageId in {etype} event"
                                    message_ids.add(event["messageId"])
                            except json.JSONDecodeError:
                                pass
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(), "events": events, "response": ""}
    except Exception as e:
        return {"error": str(e), "events": events, "response": ""}

    return {
        "events": events,
        "response": "".join(tokens)[:500],
        "token_count": len(tokens),
        "message_ids": message_ids,
    }


def test(description: str, query: str, checks: list[str]) -> bool:
    """Run a scenario and check expectations."""
    print(f"\n{'='*60}")
    print(f"📋 {description}")
    print(f"💬 Query: {query[:80]}...")
    result = stream_query(query)

    if "error" in result:
        print(f"  ❌ ERROR: {result['error'][:200]}")
        return False

    events = result["events"]
    print(f"  Events: delta={events['message.delta']} tool_call={events['message.tool_call']} chart={events['chart']} error={events['error']}")
    print(f"  MessageIds collected: {len(result.get('message_ids', set()))}")
    print(f"  Response: {result['response'][:200]}...")

    passed = True
    for check in checks:
        if check == "search_used":
            ok = events["message.tool_call"] > 0
            print(f"  {'✅' if ok else '❌'} search_used: {events['message.tool_call']} tool calls")
            passed = passed and ok
        elif check == "chart_generated":
            ok = events["chart"] > 0
            print(f"  {'✅' if ok else '❌'} chart_generated: {events['chart']} chart events")
            passed = passed and ok
        elif check == "no_tools":
            ok = events["message.tool_call"] == 0
            print(f"  {'✅' if ok else '❌'} no_tools: {events['message.tool_call']} unexpected tool calls")
            passed = passed and ok
        elif check == "has_response":
            ok = len(result["response"]) > 10
            print(f"  {'✅' if ok else '❌'} has_response: {len(result['response'])} chars")
            passed = passed and ok
        elif check == "no_error":
            ok = events["error"] == 0
            print(f"  {'✅' if ok else '❌'} no_error")
            passed = passed and ok
        elif check.startswith("token_min:"):
            min_tokens = int(check.split(":")[1])
            ok = events["message.delta"] >= min_tokens
            print(f"  {'✅' if ok else '❌'} token_min:{min_tokens}: {events['message.delta']} delta events")
            passed = passed and ok

    return passed


def main():
    print("=" * 60)
    print("🤖 LLM Chat Scenario Tests")
    print("=" * 60)

    results = []

    # Scenario 1: Simple greeting (no tools needed)
    results.append(test(
        "Scenario 1: Simple greeting",
        "你好，请用一句话介绍你自己",
        ["has_response", "no_tools", "no_error"],
    ))

    # Scenario 2: Search query (should use search tool)
    results.append(test(
        "Scenario 2: Web search",
        "搜索一下2026年6月的科技新闻",
        ["search_used", "has_response", "no_error"],
    ))

    # Scenario 3: Chart generation
    results.append(test(
        "Scenario 3: Chart visualization",
        "对比一下Python、Java、Go三种语言的优缺点，使用图表展示",
        ["has_response", "no_error"],
    ))

    # Scenario 4: Time query
    results.append(test(
        "Scenario 4: Time query",
        "现在几点？今天是星期几？",
        ["has_response", "no_error"],
    ))

    # Scenario 5: Code execution
    results.append(test(
        "Scenario 5: Python code execution",
        "使用Python计算1到100的累加和，然后用文字告诉我结果",
        ["has_response", "no_error", "token_min:20"],
    ))

    # Scenario 6: Data analysis (multi-tool scenario)
    results.append(test(
        "Scenario 6: Data analysis with search",
        "搜索2024年全球GDP排名前5的国家，然后用柱状图展示",
        ["search_used", "has_response", "no_error"],
    ))

    # Summary
    print(f"\n{'='*60}")
    passed = sum(results)
    total = len(results)
    print(f"📊 Results: {passed}/{total} passed")
    for i, r in enumerate(results):
        print(f"  Scenario {i+1}: {'✅' if r else '❌'}")
    print(f"{'='*60}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
