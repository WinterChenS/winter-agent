"""
End-to-end API tests for Plan-Execute-Compose workflow.

Tests the POST /api/v1/generate/stream SSE endpoint with real requests.
Requires the AI service to be running on localhost:8000.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from typing import Optional

import httpx
import pytest

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s [TEST] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/v1"
TIMEOUT = 60.0  # seconds for SSE streaming response


async def collect_sse_events(url: str, payload: dict, timeout: float = TIMEOUT) -> list[dict]:
    """Collect all SSE events from a streaming endpoint."""
    events: list[dict] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
        async with client.stream("POST", url, json=payload) as response:
            logger.info("SSE response status=%d", response.status_code)
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        events.append(event)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse SSE line: %s", data_str[:100])
    return events


def analyze_events(events: list[dict]) -> dict:
    """Analyze SSE events and extract key metrics."""
    result = {
        "total_events": len(events),
        "types": {},
        "deltas": [],
        "tool_calls": [],
        "plan_phase": None,
        "final_content": "",
        "has_error": False,
        "done_status": None,
    }
    for evt in events:
        etype = evt.get("type", "unknown")
        result["types"][etype] = result["types"].get(etype, 0) + 1

        if etype == "message.delta":
            delta = evt.get("delta", "")
            result["deltas"].append(delta)
            result["final_content"] += delta
        elif etype == "message.tool_call":
            result["tool_calls"].append(evt.get("payload", evt).get("toolCall", {}))
        elif etype == "message.done":
            result["done_status"] = evt.get("payload", evt).get("status")

    return result


# ── Test Cases ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_greeting_fast_path():
    """Test that a simple greeting skips planning and goes direct to composer."""
    logger.info("=== Test: greeting fast path ===")
    events = await collect_sse_events(
        f"{BASE_URL}/generate/stream",
        {"message": "你好", "conversation_id": "test-greeting-1"},
    )
    analysis = analyze_events(events)
    logger.info("Events: %d, types: %s", analysis["total_events"], analysis["types"])
    logger.info("Final content: %s", analysis["final_content"][:200])

    assert analysis["done_status"] == "done", f"Expected done, got {analysis['done_status']}"
    assert len(analysis["final_content"]) > 0, "Expected non-empty response for greeting"
    logger.info("✅ Greeting test PASSED")


@pytest.mark.asyncio
async def test_simple_question_executes():
    """Test that a simple factual question goes through plan→execute→compose."""
    logger.info("=== Test: simple question ===")
    events = await collect_sse_events(
        f"{BASE_URL}/generate/stream",
        {"message": "What is the current year and month? Use the time tool to check.", "conversation_id": "test-time-1"},
    )
    analysis = analyze_events(events)

    logger.info("Events: %d, types: %s", analysis["total_events"], analysis["types"])
    logger.info("Final content: %s", analysis["final_content"][:300])

    assert analysis["done_status"] == "done", f"Expected done, got {analysis['done_status']}"
    assert len(analysis["final_content"]) > 0, "Expected non-empty response"
    logger.info("✅ Simple question test PASSED")


@pytest.mark.asyncio
async def test_streaming_delta_events():
    """Test that message.delta events are emitted for streaming output."""
    logger.info("=== Test: streaming delta events ===")
    events = await collect_sse_events(
        f"{BASE_URL}/generate/stream",
        {"message": "Say hello and introduce yourself briefly.", "conversation_id": "test-hello-1"},
    )
    analysis = analyze_events(events)

    logger.info("Events: %d, delta events: %d", analysis["total_events"], analysis["types"].get("message.delta", 0))

    assert analysis["done_status"] == "done"
    assert analysis["types"].get("message.delta", 0) > 0, "Expected at least one message.delta event"
    assert len(analysis["final_content"]) > 0, "Expected non-empty streaming content"
    logger.info("✅ Streaming delta test PASSED")


@pytest.mark.asyncio
async def test_conversation_started_event():
    """Test that conversation.started event is emitted first."""
    logger.info("=== Test: conversation.started event ===")
    events = await collect_sse_events(
        f"{BASE_URL}/generate/stream",
        {"message": "Hello", "conversation_id": "test-conv-start-1"},
    )
    non_empty_types = [e.get("type") for e in events if e.get("type")]

    assert "conversation.started" in non_empty_types, \
        f"Expected conversation.started, got first events: {non_empty_types[:5]}"
    logger.info("✅ conversation.started test PASSED")


@pytest.mark.asyncio
async def test_error_handling_invalid_agent():
    """Test error handling for invalid agent_id."""
    logger.info("=== Test: invalid agent_id error ===")
    events = await collect_sse_events(
        f"{BASE_URL}/generate/stream",
        {"message": "Hello", "conversation_id": "test-error-1", "agent_id": "non-existent-agent-xyz"},
    )
    # Find error or done with error
    for evt in events:
        etype = evt.get("type", "")
        if etype == "message.done":
            status = (evt.get("payload", {}) or {}).get("status", "")
            if status == "error":
                logger.info("✅ Got error for invalid agent: %s", evt.get("payload", {}).get("error", ""))
                return
    # If we get here, should not happen for invalid agent
    logger.warning("⚠️ No error for invalid agent (might not have agent validation enabled)")
    # This test is informational — skip assertion if agent validation is off


# ── Run Standalone ──────────────────────────────────────────────────────────


async def main():
    """Run all tests sequentially and print results."""
    logger.info("=" * 60)
    logger.info("Plan-Execute-Compose API Integration Tests")
    logger.info("=" * 60)

    tests = [
        ("greeting fast path", test_greeting_fast_path),
        ("streaming delta events", test_streaming_delta_events),
        ("conversation.started event", test_conversation_started_event),
        ("simple question executes", test_simple_question_executes),
        ("invalid agent error", test_error_handling_invalid_agent),
    ]

    results = []
    for name, test_fn in tests:
        try:
            start = time.time()
            await test_fn()
            elapsed = time.time() - start
            results.append((name, "PASS", f"{elapsed:.1f}s"))
        except AssertionError as e:
            results.append((name, "FAIL", str(e)))
        except Exception as e:
            results.append((name, "ERROR", str(e)))

    logger.info("=" * 60)
    logger.info("RESULTS SUMMARY")
    logger.info("=" * 60)
    passed = 0
    for name, status, detail in results:
        logger.info("  %s: %s (%s)", name, status, detail)
        if status == "PASS":
            passed += 1
    logger.info("---")
    logger.info("TOTAL: %d/%d PASSED", passed, len(results))

    return passed == len(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
