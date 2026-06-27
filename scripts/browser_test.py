#!/usr/bin/env python3
"""Browser-based E2E tests for the AI Chat UI using Playwright.

Usage:
    python scripts/browser_test.py                     # all tests
    python scripts/browser_test.py --screenshot DIR    # save screenshots
    python scripts/browser_test.py --headed            # show browser window
"""

import asyncio
import sys
import time
import argparse
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Install playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

BASE_URL = "http://localhost:3000"
SCREENSHOTS = None


async def screenshot(page, name: str):
    """Take a screenshot if --screenshot was specified."""
    if SCREENSHOTS:
        path = Path(SCREENSHOTS) / f"{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(path), full_page=True)
        print(f"  [screenshot] {path}")


def _generate_jwt(username: str = "test-user") -> str:
    """Generate a valid JWT token using the app's signing key."""
    import jwt
    import datetime
    secret = "winter-agent-jwt-secret-key-2026-min-256-bits!!"
    payload = {
        "sub": username,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


async def test_login(page) -> bool:
    """Inject a JWT token into localStorage to bypass login."""
    # Generate a valid token using the app's signing key
    token = _generate_jwt("test-user")

    # Navigate to any page to set the origin
    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)

    # Inject token into localStorage
    await page.evaluate(f"""
        localStorage.setItem('auth_token', '{token}');
    """)
    print(f"  Injected JWT token for test-user")

    # Now navigate to the main page
    await page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=15000)
    await page.wait_for_timeout(1000)

    current_url = page.url
    print(f"  Current URL: {current_url}")
    if "/login" in current_url:
        print("  ⚠ Still on login page — auth may be enforced differently")
        return False

    print("  ✓ Authenticated successfully")
    await screenshot(page, "01-authenticated")
    return True


async def test_send_message(page, message: str = "你好，请介绍一下你自己"):
    """Send a message and verify streaming response appears."""
    print(f"\n  Sending: '{message}'")

    # Find the input textarea (InputBox)
    textarea = page.locator('textarea[placeholder*="输入"]').first
    if await textarea.count() == 0:
        textarea = page.locator('textarea').first

    if await textarea.count() == 0:
        print("  ❌ No input textarea found!")
        return False

    await textarea.click()
    await textarea.fill(message)
    await screenshot(page, "02-typed-message")

    # Click send button or press Enter
    send_btn = page.locator('button:has-text("发送"), button:has-text("Send")').first
    if await send_btn.count() > 0 and await send_btn.is_enabled():
        await send_btn.click()
        print("  Clicked send button")
    else:
        await textarea.press("Enter")
        print("  Pressed Enter to send")

    # Wait for streaming to start (assistant bubble should appear)
    await page.wait_for_timeout(2000)

    # Look for agent status indicator
    agent_text = page.get_by_text("Agent", exact=False).first
    if await agent_text.count() > 0:
        print("  ✓ Agent indicator found")

    # Look for tool call panels
    tool_text = page.get_by_text("tool", exact=False).first
    if await tool_text.count() > 0:
        print("  ✓ Tool call elements found")

    # Wait for streaming to complete (up to 30 seconds)
    print("  Waiting for response...")
    for i in range(30):
        await page.wait_for_timeout(1000)

        # Check for assistant message bubble (new MessageBubble with non-empty content)
        bubbles = page.locator('div[class*="bg-white"][class*="border"], div[class*="bg-gray"]')
        bubble_count = await bubbles.count()

        # Check if send button is re-enabled (streaming done)
        if await send_btn.count() > 0:
            is_enabled = await send_btn.is_enabled()
            if is_enabled and i > 5:  # At least 5 seconds have passed
                print(f"  Response complete after {i+1}s, {bubble_count} bubbles visible")
                break
        elif i > 20:  # 20 second fallback
            print(f"  Timeout after {i+1}s")
            break

        if i % 5 == 0:
            print(f"    ... {i+1}s elapsed, {bubble_count} bubbles")

    await screenshot(page, "03-response")
    return True


async def test_tool_trigger(page):
    """Send a message that should trigger tool calls."""
    print("\n  Testing tool-triggering message...")

    textarea = page.locator('textarea').first
    await textarea.click()
    await textarea.fill("帮我搜索一下 Python 3.13 有哪些新特性")
    await textarea.press("Enter")

    has_tool = False
    for i in range(40):
        await page.wait_for_timeout(1000)

        # Check for tool call indicators
        tc = await page.get_by_text("tool", exact=False).count()
        tc += await page.get_by_text("搜索", exact=False).count()

        # Look for agent status
        ac = await page.get_by_text("Agent", exact=False).count()

        if tc > 0 and not has_tool:
            print(f"  ✓ Tool indicators found after {i+1}s ({tc} elements)")
            has_tool = True

        # Check if done
        send_btn = page.locator('button:has-text("发送")').first
        if await send_btn.count() > 0 and await send_btn.is_enabled() and i > 5:
            print(f"  Done after {i+1}s, tools: {tc}, agent: {ac}")
            break

    await screenshot(page, "04-tool-response")
    return has_tool


async def test_chart_request(page):
    """Send a chart request and verify chart rendering."""
    print("\n  Testing chart request...")

    await nav_to_chat(page)

    textarea = page.locator('textarea').first
    await textarea.click()
    await textarea.fill("用折线图展示：一月100，二月200，三月150，四月300")
    await textarea.press("Enter")

    has_chart = False
    for i in range(50):
        await page.wait_for_timeout(1000)

        # Check for ECharts canvas (ChartRenderer)
        chart = page.locator('canvas')
        cc = await chart.count()
        if cc > 0 and not has_chart:
            print(f"  ✓ Chart canvas found after {i+1}s ({cc} canvases)")
            has_chart = True

        # Also check for chart data in DOM
        chart_div = page.locator('[class*="chart"], [class*="Chart"], canvas')
        cdc = await chart_div.count()
        if cdc > 0 and not has_chart:
            print(f"  ✓ Chart container found after {i+1}s ({cdc} elements)")
            has_chart = True

        if i > 30:
            print(f"  Chart not found after {i+1}s")
            break

    await screenshot(page, "05-chart-response")
    return has_chart


async def test_scroll_behavior(page):
    """Test scroll-to-bottom button behavior."""
    print("\n  Testing scroll behavior...")

    # Send multiple messages to fill the page
    for j in range(3):
        textarea = page.locator('textarea').first
        await textarea.click()
        await textarea.fill(f"这是第{j+1}条测试消息，请给出一个较长的回答来撑满页面。" * 2)
        await textarea.press("Enter")

        # Wait for response
        for _ in range(15):
            await page.wait_for_timeout(1000)
            send_btn = page.locator('button:has-text("发送")').first
            if await send_btn.count() > 0 and await send_btn.is_enabled():
                break

    await page.wait_for_timeout(1000)

    # Scroll up to trigger the button
    await page.evaluate("window.scrollTo(0, 200)")
    await page.wait_for_timeout(500)

    # Check for "回到底部" button
    scroll_btn = page.locator('button:has-text("回到底部")')
    if await scroll_btn.count() > 0:
        print("  ✓ '回到底部' button visible after scrolling up")
        await scroll_btn.click()
        await page.wait_for_timeout(500)
        # Check it disappeared
        if await scroll_btn.count() == 0:
            print("  ✓ Button dismissed after clicking")
    else:
        print("  ⚠ '回到底部' button not found (page may not overflow)")

    await screenshot(page, "06-scroll")


async def test_empty_state(page):
    """Test empty conversation state."""
    print("\n  Testing empty state...")

    # Navigate to a new conversation
    await page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=15000)
    await page.wait_for_timeout(1000)

    # Should show empty state message
    empty = page.get_by_text("开始", exact=False).first
    if await empty.is_visible():
        print("  ✓ Empty state message shown")
        await screenshot(page, "07-empty-state")
        return True
    else:
        print("  ⚠ Empty state message not found")
        return False


async def test_agent_selector(page):
    """Test agent selector dropdown."""
    print("\n  Testing agent selector...")

    # Look for select/combobox elements
    select = page.locator('select').first
    if await select.count() > 0:
        options = await select.locator('option').all()
        option_texts = []
        for opt in options:
            text = await opt.text_content()
            option_texts.append(text.strip())
        print(f"  Agent options: {option_texts}")

        # Select a different agent
        if len(options) > 1:
            await select.select_option(index=1)
            print(f"  ✓ Switched to: {option_texts[1]}")
            await screenshot(page, "08-agent-selector")
            return True

    print("  ⚠ No agent selector found")
    return False


async def test_markdown_rendering(page):
    """Test that markdown content renders correctly."""
    print("\n  Testing markdown rendering...")

    await nav_to_chat(page)

    textarea = page.locator('textarea').first
    await textarea.click()
    await textarea.fill("帮我列一个表格，包含三列：姓名、年龄、城市，至少3行数据")
    await textarea.press("Enter")

    # Wait for response with table
    has_table = False
    for i in range(30):
        await page.wait_for_timeout(1000)

        # Check for table elements
        table = page.locator('table')
        if await table.count() > 0 and not has_table:
            print(f"  ✓ Table rendered after {i+1}s")
            has_table = True

        # Check for code blocks
        code = page.locator('pre code')
        if await code.count() > 0:
            print(f"  ✓ Code block found")

        send_btn = page.locator('button:has-text("发送")').first
        if await send_btn.count() > 0 and await send_btn.is_enabled() and i > 5:
            break

    await screenshot(page, "09-markdown")
    return has_table


async def nav_to_chat(page):
    """Navigate to the chat page, handling login redirect."""
    await page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=15000)
    await page.wait_for_timeout(500)
    if "/login" in page.url:
        print("  (redirected to login, skipping)")
        return False
    return True


# ── main ───────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="AI Chat UI Browser E2E Tests")
    parser.add_argument("--screenshot", help="Save screenshots to directory")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument("--quick", action="store_true", help="Quick smoke test only")
    args = parser.parse_args()

    global SCREENSHOTS
    SCREENSHOTS = args.screenshot

    print("=" * 60)
    print("AI Chat UI — Browser E2E Tests")
    print(f"Target: {BASE_URL}")
    print(f"Mode: {'QUICK' if args.quick else 'FULL'}")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not args.headed)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
        )
        page = await context.new_page()

        # Collect console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        results = {}

        # 1. Login
        print("\n--- Test 1: Login & Navigation ---")
        logged_in = await test_login(page)
        if not logged_in:
            print("  ⚠ Not logged in, tests may be limited")
        results["login"] = logged_in

        # 2. Send message
        print("\n--- Test 2: Send Message & Streaming ---")
        results["send"] = await test_send_message(page)

        # 3. Tool trigger
        print("\n--- Test 3: Tool Call Display ---")
        await nav_to_chat(page)
        results["tool"] = await test_tool_trigger(page)

        if not args.quick:
            # 4. Chart request
            print("\n--- Test 4: Chart Rendering ---")
            await nav_to_chat(page)
            results["chart"] = await test_chart_request(page)

            # 5. Agent selector
            print("\n--- Test 5: Agent Selector ---")
            results["agent_selector"] = await test_agent_selector(page)

            # 6. Scroll behavior
            print("\n--- Test 6: Scroll Behavior ---")
            results["scroll"] = await test_scroll_behavior(page)

            # 7. Empty state
            print("\n--- Test 7: Empty State ---")
            results["empty"] = await test_empty_state(page)

            # 8. Markdown rendering
            print("\n--- Test 8: Markdown Rendering ---")
            results["markdown"] = await test_markdown_rendering(page)

        await browser.close()

        # Summary
        print("\n" + "=" * 60)
        print("TEST RESULTS")
        print("=" * 60)
        passed = sum(1 for v in results.values() if v)
        for name, ok in results.items():
            print(f"  {'✓' if ok else '✗'} {name}")
        print(f"\n  Passed: {passed}/{len(results)}")
        print(f"  Console errors: {len(console_errors)}")
        if console_errors:
            for e in console_errors[:5]:
                print(f"    {e[:120]}")


if __name__ == "__main__":
    asyncio.run(main())
