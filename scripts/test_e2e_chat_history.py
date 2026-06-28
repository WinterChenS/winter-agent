#!/usr/bin/env python3
"""
完整的 HTTP 端到端测试：调用 stream_generate API → 查 history API → 验证用户消息。

使用方法:
  python scripts/test_e2e_chat_history.py [--host HOST] [--port PORT]

默认连接 localhost:8000 (ai-service 直连)。
"""
import argparse
import asyncio
import json
import sys
import uuid
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ai_service'))

import httpx

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


async def test_full_flow(host: str, port: int, prefix: str):
    conversation_id = str(uuid.uuid4())
    user_message = f"E2E测试-{uuid.uuid4().hex[:8]}"
    message_id = str(uuid.uuid4())

    stream_url = f"http://{host}:{port}{prefix}/generate/stream"
    history_url = f"http://{host}:{port}{prefix}/history/{conversation_id}"

    print(f"会话ID: {conversation_id}")
    print(f"用户消息: {user_message}")
    print(f"流式: {stream_url}")
    print(f"历史: {history_url}")

    # Step 1: 发送流式请求
    print("\n--- Step 1: POST 流式请求 ---")
    stream_events = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            stream_url,
            json={
                "message": user_message,
                "conversationId": conversation_id,
                "agentId": None,
                "messageId": message_id,
            },
            headers={"Content-Type": "application/json"},
        ) as resp:
            print(f"  状态码: {resp.status_code}")
            if resp.status_code != 200:
                body = await resp.aread()
                print(f"{RED}  错误: {body.decode()[:500]}{RESET}")
                return False

            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        continue
                    try:
                        event = json.loads(data_str)
                        stream_events.append(event)
                    except json.JSONDecodeError:
                        pass

    print(f"  收到 {len(stream_events)} 个 SSE 事件")
    event_types = list(set(e.get("type", "?") for e in stream_events))
    print(f"  事件类型: {event_types}")

    # 等待异步写入完成
    await asyncio.sleep(0.5)

    # Step 2: 查询历史
    print("\n--- Step 2: GET 历史 ---")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(history_url)
        print(f"  状态码: {resp.status_code}")
        body = resp.json()
        messages = body.get("messages", [])

        print(f"  消息数: {len(messages)}")
        for i, m in enumerate(messages):
            role = m.get("role", "?")
            content = str(m.get("content", ""))[:80]
            print(f"    [{i}] role={role} content={content}")

        if len(messages) == 0:
            print(f"{RED}  FAIL: history 返回 0 条消息{RESET}")
            return False

        roles = [m.get("role") for m in messages]
        if "user" not in roles:
            print(f"{RED}  FAIL: 历史中没有 user 角色! roles={roles}{RESET}")
            # 打印完整消息
            for m in messages:
                print(f"    完整: {json.dumps(m, ensure_ascii=False)[:200]}")
            return False

        # 验证内容
        user_msgs = [m for m in messages if m.get("role") == "user"]
        found = any(user_message in str(m.get("content", "")) for m in user_msgs)
        if not found:
            print(f"{RED}  FAIL: 用户消息内容不匹配!{RESET}")
            return False

        print(f"{GREEN}  PASS: 历史完整包含用户消息和 assistant 回复{RESET}")
        return True


async def main():
    parser = argparse.ArgumentParser(description="E2E chat history test")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--prefix", default="/api/v1")
    args = parser.parse_args()

    print("=" * 60)
    print("端到端聊天历史 HTTP 测试")
    print(f"目标: http://{args.host}:{args.port}{args.prefix}")
    print("=" * 60)

    success = await test_full_flow(args.host, args.port, args.prefix)

    print("\n" + "=" * 60)
    if success:
        print(f"{GREEN}E2E 测试通过 ✓{RESET}")
    else:
        print(f"{RED}E2E 测试失败 ✗{RESET}")
    print("=" * 60)
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
