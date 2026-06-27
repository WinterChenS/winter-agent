#!/usr/bin/env python3
"""Test data_analyst agent: verify it calls execute_python and generates images."""

import asyncio, json, httpx, sys
from collections import Counter


async def test_chart(agent_id: str, message: str) -> dict:
    """Send a chart request and return test results."""
    body = {
        "message": message,
        "agentId": agent_id,
        "messageId": f"test-{agent_id}",
        "stream": True,
    }
    print(f"\n{'='*60}")
    print(f"Testing [{agent_id}]: {message}")
    print(f"{'='*60}")

    result = {
        "ok": True,
        "errors": [],
        "tool_calls": Counter(),
        "image_uploads": 0,
        "image_urls": [],
        "deltas": 0,
        "full_text": "",
        "events": [],
    }

    async with httpx.AsyncClient(timeout=180, verify=False) as c:
        try:
            async with c.stream(
                "POST", "http://localhost:8000/api/v1/generate/stream", json=body
            ) as r:
                if r.status_code != 200:
                    result["errors"].append(f"HTTP {r.status_code}")
                    result["ok"] = False
                    return result

                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    d = line[6:] if line.startswith("data: ") else line[5:]
                    try:
                        e = json.loads(d)
                        t = e.get("type", "")
                        result["events"].append(t)

                        if t == "tool.started":
                            tool = e["payload"]["tool"]
                            result["tool_calls"][tool] += 1
                            print(f"  [TOOL START] {tool}")

                        elif t == "tool.finished":
                            tool = e["payload"]["tool"]
                            res = str(e["payload"].get("result", ""))
                            has_images = "images" in res and "'images': {}" not in res
                            has_upload = "[图片已上传]" in res
                            has_savefig = "plt.savefig" in res
                            print(f"  [TOOL DONE] {tool} images={has_images} upload={has_upload}")

                        elif t == "tool.failed":
                            tool = e["payload"]["tool"]
                            err = str(e["payload"].get("error", ""))[:150]
                            result["errors"].append(f"Tool {tool} failed: {err}")
                            result["ok"] = False
                            print(f"  [TOOL FAIL] {tool}: {err}")

                        elif t == "image.uploaded":
                            url = e["payload"].get("url", "")
                            result["image_uploads"] += 1
                            result["image_urls"].append(url)
                            print(f"  [IMAGE] {url[:100]}")

                        elif t == "message.delta":
                            result["deltas"] += 1
                            result["full_text"] += e.get("delta", "")

                        elif t == "message.done":
                            break

                        elif t == "error":
                            err = str(e.get("error", "") or e.get("payload", {}).get("error", ""))
                            result["errors"].append(f"SSE error: {err[:150]}")
                            result["ok"] = False
                            break

                    except json.JSONDecodeError:
                        pass

        except Exception as ex:
            result["errors"].append(f"Connection: {ex}")
            result["ok"] = False

    return result


def analyze(result: dict):
    """Analyze test results and print verdict."""
    tc = result["tool_calls"]
    print(f"\n  Tools called: {dict(tc)}")
    print(f"  Image uploads: {result['image_uploads']}")
    print(f"  Text deltas: {result['deltas']}")
    print(f"  Errors: {len(result['errors'])}")

    # Check execute_python was called
    if tc.get("execute_python", 0) == 0:
        print(f"  ❌ FAIL: execute_python was NEVER called!")
        result["ok"] = False

    # Check images were generated
    if result["image_uploads"] == 0:
        print(f"  ❌ FAIL: No images generated (plt.savefig not called)")
        result["ok"] = False

    # Check text was streamed
    if result["deltas"] < 10:
        print(f"  ⚠ WARN: Very few deltas ({result['deltas']})")

    if result["ok"] and not result["errors"]:
        print(f"  ✅ PASS")
    elif result["errors"]:
        print(f"  ❌ FAIL: {result['errors']}")

    return result["ok"]


async def main():
    # Kill old service, restart fresh
    import os, subprocess, time
    subprocess.run(["kill", "$(lsof", "-ti:8000)"], shell=True, capture_output=True)
    time.sleep(2)
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--app-dir",
         "/Volumes/work/projects/winter-agent/ai_service",
         "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd="/Volumes/work/projects/winter-agent/ai_service"
    )
    time.sleep(5)

    # Check service
    async with httpx.AsyncClient(timeout=5) as c:
        try:
            r = await c.get("http://localhost:8000/api/v1/agents/")
            if r.status_code != 200:
                print("Service not ready!")
                return 1
        except Exception:
            print("Service not running!")
            return 1

    all_ok = True

    # Test 1: data-analyst with simple chart data
    r = await test_chart(
        "data-analyst",
        "用折线图展示以下数据：1月裁员5000人，2月8000人，3月12000人，4月10000人，5月7000人，6月9000人"
    )
    all_ok &= analyze(r)

    # Test 2: data-analyst with search + chart
    r = await test_chart(
        "general",
        "画柱状图展示北京200万、上海250万、广州180万、深圳220万的人口数据"
    )
    all_ok &= analyze(r)

    print(f"\n{'='*60}")
    print(f"OVERALL: {'✅ PASS' if all_ok else '❌ FAIL'}")
    print(f"{'='*60}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
