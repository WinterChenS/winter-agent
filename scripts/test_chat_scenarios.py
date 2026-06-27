#!/usr/bin/env python3
"""
Comprehensive test suite for the AI Chat Streaming API.
Covers: basic chat, agent routing, tool calls, error handling, edge cases.

Usage:
    python scripts/test_chat_scenarios.py              # all tests
    python scripts/test_chat_scenarios.py --quick       # smoke test only
    python scripts/test_chat_scenarios.py --verbose     # show all SSE events
"""

import asyncio
import json
import sys
import time
import argparse
from collections import Counter

import httpx

BASE_URL = "http://localhost:8000/api/v1"
TIMEOUT = 120.0

# ── helpers ────────────────────────────────────────────────────────────────

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.errors: list[str] = []
        self.events: list[dict] = []
        self.event_types: list[str] = []
        self.duration_ms = 0
        self.token_count = 0

    def fail(self, msg: str):
        self.passed = False
        self.errors.append(msg)

    def log_event(self, event: dict):
        self.events.append(event)
        self.event_types.append(event.get("type", "unknown"))

    def has_event(self, event_type: str) -> bool:
        return event_type in self.event_types

    def count_event(self, event_type: str) -> int:
        return self.event_types.count(event_type)

    @property
    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        parts = [f"{status} {self.name}"]
        parts.append(f"     events={len(self.events)} tokens={self.token_count} duration={self.duration_ms}ms")
        tc = Counter(self.event_types)
        parts.append(f"     types={dict(tc)}")
        if self.errors:
            for e in self.errors:
                parts.append(f"     ERR: {e}")
        return "\n".join(parts)


async def stream_chat(
    message: str,
    agent_id: str | None = None,
    conversation_id: str | None = None,
) -> TestResult:
    """Send a chat message and collect all SSE events."""
    name = message[:30] + ("..." if len(message) > 30 else "")
    if agent_id:
        name = f"[{agent_id}] {name}"
    result = TestResult(name)
    t0 = time.time()

    body = {
        "message": message,
        "conversationId": conversation_id,
        "agentId": agent_id,
        "messageId": f"test-{id(message)}",
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            async with client.stream(
                "POST", f"{BASE_URL}/generate/stream",
                json=body,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status_code != 200:
                    result.fail(f"HTTP {resp.status_code}")
                    return result

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                    elif line.startswith("data:"):
                        data_str = line[5:]
                    else:
                        continue

                    try:
                        event = json.loads(data_str)
                        etype = event["type"]
                        result.log_event(event)

                        if etype == "message.delta":
                            result.token_count += 1
                        elif etype == "message.done":
                            break
                        elif etype == "error":
                            err = event.get("error") or event.get("payload", {}).get("error", "")
                            result.fail(f"SSE error: {err[:100]}")
                            break

                    except json.JSONDecodeError:
                        pass

        except httpx.ConnectError:
            result.fail("Connection refused — AI service not running on port 8000?")
        except Exception as e:
            result.fail(f"{type(e).__name__}: {e}")

    result.duration_ms = int((time.time() - t0) * 1000)
    return result


# ── assertions ─────────────────────────────────────────────────────────────

def assert_has_events(r: TestResult, *types: str):
    for t in types:
        if not r.has_event(t):
            r.fail(f"missing event: {t}")

def assert_event_order(r: TestResult, *types: str):
    idx = 0
    for t in r.event_types:
        if idx < len(types) and t == types[idx]:
            idx += 1
    if idx < len(types):
        r.fail(f"events not in order: need {list(types)}, got {r.event_types[:25]}")

def assert_no_error(r: TestResult):
    if r.has_event("error"):
        r.fail("unexpected error event")

def assert_token_count(r: TestResult, min_tokens: int = 5):
    if r.token_count < min_tokens:
        r.fail(f"too few tokens: {r.token_count} < {min_tokens}")

def assert_duration_under(r: TestResult, max_ms: int = 60000):
    if r.duration_ms > max_ms:
        r.fail(f"too slow: {r.duration_ms}ms > {max_ms}ms")


# ── test cases ─────────────────────────────────────────────────────────────

async def test_basic_greeting():
    """Simple greeting — no tools, direct answer"""
    r = await stream_chat("你好")
    assert_no_error(r)
    assert_has_events(r, "conversation.started", "message.delta", "message.done")
    assert_token_count(r, 10)
    assert_duration_under(r, 30000)
    return r


async def test_search_with_agent():
    """Search agent via keyword match → tool calls"""
    r = await stream_chat("帮我搜索一下 Python 3.13 有哪些新特性", agent_id="srch-agent")
    assert_no_error(r)
    assert_has_events(r, "conversation.started", "agent.started",
                      "tool.started", "tool.finished",
                      "agent.finished", "message.delta", "message.done")
    assert_event_order(r, "agent.started", "tool.started", "tool.finished",
                       "agent.finished", "message.delta", "message.done")
    assert_token_count(r, 20)
    return r


async def test_search_no_agent_id():
    """No agent specified — RouterAgent auto-matches"""
    r = await stream_chat("帮我查一下最近的科技新闻")
    assert_no_error(r)
    assert_has_events(r, "message.delta", "message.done")
    assert_token_count(r, 10)
    return r


async def test_invalid_agent_id():
    """Non-existent agentId → error event"""
    r = await stream_chat("任意问题", agent_id="non-existent-agent-xyz")
    if not r.has_event("error"):
        r.fail("expected error event for invalid agentId")
    assert_has_events(r, "message.done")
    return r


async def test_code_analyst_agent():
    """Code analyst — triggers execute_python tool"""
    r = await stream_chat("帮我计算 1 到 100 的累加和是多少", agent_id="code-analyst")
    assert_no_error(r)
    assert_has_events(r, "agent.started", "agent.finished",
                      "message.delta", "message.done")
    assert_token_count(r, 5)
    return r


async def test_general_agent():
    """General assistant — has all tools"""
    r = await stream_chat("搜索最新的 AI 新闻并总结", agent_id="general")
    assert_no_error(r)
    assert_has_events(r, "agent.started", "agent.finished",
                      "message.delta", "message.done")
    assert_token_count(r, 10)
    return r


async def test_web_researcher_agent():
    """Web researcher — browse + search tools"""
    r = await stream_chat("帮我看看 github.com 首页有什么内容", agent_id="web-search")
    assert_no_error(r)
    assert_has_events(r, "agent.started", "agent.finished",
                      "message.delta", "message.done")
    assert_token_count(r, 5)
    return r


async def test_multiple_turns():
    """Same conversationId — multi-turn conversation"""
    conv_id = f"conv-test-{int(time.time() * 1000)}"

    r1 = await stream_chat("你好，我叫小明", conversation_id=conv_id)
    assert_no_error(r1)
    assert_token_count(r1, 5)

    r2 = await stream_chat("我叫什么名字？", conversation_id=conv_id)
    assert_no_error(r2)
    assert_token_count(r2, 3)

    return [r1, r2]


async def test_empty_message():
    """Empty message — should not hang"""
    r = await stream_chat("")
    assert_duration_under(r, 30000)
    return r


async def test_long_message():
    """Long message — no truncation"""
    long_msg = "请详细分析人工智能在医疗领域的应用和发展前景，" * 20
    r = await stream_chat(long_msg)
    assert_no_error(r)
    assert_duration_under(r, 120000)
    return r


async def test_event_timing():
    """Events should arrive promptly, not all at the end"""
    r = await stream_chat("帮我搜索量子计算最新进展", agent_id="srch-agent")
    assert_no_error(r)

    if r.events:
        first = r.events[0]
        if not first.get("timestamp"):
            r.fail("events missing timestamp field")

    # First event should arrive within 10s
    if r.duration_ms > 10000 and len(r.events) > 1:
        dt_first = (r.events[0].get("timestamp", 0) - r.events[1].get("timestamp", 0))
        if abs(dt_first) < 100:
            r.fail("all events arrived at same time — no real-time streaming")

    return r


async def test_parallel_requests():
    """4 concurrent requests — no interference"""
    queries = [
        ("你好，介绍一下你自己", None),
        ("搜索 Python asyncio 用法", "srch-agent"),
        ("React 18 有什么新特性", None),
        ("计算 2 的 10 次方", "code-analyst"),
    ]

    results = await asyncio.gather(
        *[stream_chat(msg, agent_id=aid) for msg, aid in queries],
        return_exceptions=True,
    )

    passed = 0
    for r in results:
        if isinstance(r, TestResult) and r.passed:
            passed += 1

    result = TestResult("parallel-requests")
    if passed < len(queries):
        result.fail(f"only {passed}/{len(queries)} passed")
    return result


async def test_agent_switching():
    """Switch agents between turns in same conversation"""
    conv_id = f"conv-switch-{int(time.time() * 1000)}"

    r1 = await stream_chat("搜索 Python 协程最佳实践", agent_id="srch-agent", conversation_id=conv_id)
    assert_no_error(r1)
    assert_has_events(r1, "agent.started", "agent.finished")

    r2 = await stream_chat("帮我写一段代码演示协程用法", agent_id="code-analyst", conversation_id=conv_id)
    assert_no_error(r2)
    assert_has_events(r2, "agent.started", "agent.finished")

    return [r1, r2]


async def test_tool_lifecycle():
    """Verify complete tool lifecycle: started → finished"""
    r = await stream_chat("搜索最新 Go 语言版本发布时间", agent_id="srch-agent")
    assert_no_error(r)

    started = r.count_event("tool.started")
    finished = r.count_event("tool.finished")
    failed = r.count_event("tool.failed")

    if started > 0:
        if finished + failed != started:
            r.fail(f"tool lifecycle mismatch: {started} started, {finished} finished, {failed} failed")
        if finished > 0:
            # Verify each tool.started has matching tool.finished with same tool_call_id
            started_ids = []
            finished_ids = []
            for e in r.events:
                if e["type"] == "tool.started":
                    started_ids.append(e["payload"]["tool_call_id"])
                elif e["type"] == "tool.finished":
                    finished_ids.append(e["payload"]["tool_call_id"])
                elif e["type"] == "tool.failed":
                    finished_ids.append(e["payload"]["tool_call_id"])
            for sid in started_ids:
                if sid not in finished_ids:
                    r.fail(f"tool_call_id {sid} started but never finished/failed")
    else:
        # Some queries may not trigger tools — that's fine
        pass

    return r


# ── main ───────────────────────────────────────────────────────────────────

TESTS = [
    ("basic-greeting", test_basic_greeting, "简单问候，无工具"),
    ("search-agent", test_search_with_agent, "搜索助手 + 工具调用验证"),
    ("no-agent-id", test_search_no_agent_id, "Router 自动匹配 Agent"),
    ("invalid-agent", test_invalid_agent_id, "无效 AgentId 错误处理"),
    ("code-analyst", test_code_analyst_agent, "代码分析师"),
    ("general-agent", test_general_agent, "通用助手"),
    ("web-researcher", test_web_researcher_agent, "网页研究员"),
    ("multi-turn", test_multiple_turns, "多轮对话上下文"),
    ("empty-message", test_empty_message, "空消息"),
    ("long-message", test_long_message, "长消息"),
    ("event-timing", test_event_timing, "事件流时序"),
    ("parallel", test_parallel_requests, "并发请求"),
    ("agent-switching", test_agent_switching, "Agent 切换"),
    ("tool-lifecycle", test_tool_lifecycle, "Tool 生命周期完整性"),
]

SMOKE_TESTS = ["basic-greeting", "search-agent", "invalid-agent"]


async def main():
    parser = argparse.ArgumentParser(description="AI Chat Streaming API Test Suite")
    parser.add_argument("--quick", action="store_true", help="Smoke test only (3 tests)")
    args = parser.parse_args()

    test_list = SMOKE_TESTS if args.quick else [t[0] for t in TESTS]
    test_map = {t[0]: t for t in TESTS}

    print("=" * 70)
    print("AI Chat Streaming API — Test Suite")
    print(f"Target: {BASE_URL}")
    print(f"Mode: {'SMOKE' if args.quick else 'FULL'} ({len(test_list)} tests)")
    print("=" * 70)

    results: list[TestResult] = []
    all_passed = True

    for name in test_list:
        _, fn, desc = test_map[name]
        print(f"\n-- {name}: {desc}")
        try:
            res = await fn()
            if isinstance(res, list):
                for r in res:
                    print(f"  {r.summary}")
                    if not r.passed:
                        all_passed = False
                    results.append(r)
            else:
                print(f"  {res.summary}")
                if not res.passed:
                    all_passed = False
                results.append(res)
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            all_passed = False

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total_tokens = sum(r.token_count for r in results)
    total_events = sum(len(r.events) for r in results)

    print(f"  Passed:  {passed}/{len(results)}")
    print(f"  Failed:  {failed}")
    print(f"  Tokens:  {total_tokens}")
    print(f"  Events:  {total_events}")

    all_types = Counter()
    for r in results:
        all_types.update(r.event_types)
    print(f"\n  Event type distribution:")
    for etype, count in all_types.most_common():
        print(f"    {etype}: {count}")

    tool_started = all_types.get("tool.started", 0)
    tool_finished = all_types.get("tool.finished", 0)
    tool_failed = all_types.get("tool.failed", 0)
    print(f"\n  Tool calls: {tool_started} started / {tool_finished} finished / {tool_failed} failed")

    print()
    print("ALL TESTS PASSED" if all_passed else f"{failed} TEST(S) FAILED")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
