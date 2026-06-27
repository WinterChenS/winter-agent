"""
端到端测试：验证 chat_messages 表的读写完整性。
初始化独立 pool，不依赖 main.py lifespan。

使用方法：
  cd ai_service
  python tests/test_chat_message_repository.py
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from psycopg_pool import AsyncConnectionPool
from config import settings
from db.chat_message_repository import save_message, get_messages_by_conversation


async def ensure_table(pool: AsyncConnectionPool):
    """确保 chat_messages 表存在。"""
    async with pool.connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id UUID PRIMARY KEY,
                conversation_id UUID NOT NULL,
                role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL DEFAULT '',
                reasoning TEXT,
                tool_calls JSONB,
                status VARCHAR(16) DEFAULT 'done',
                agent_id VARCHAR(64),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    print("✓ chat_messages 表已确认存在")


async def test_save_and_retrieve(pool: AsyncConnectionPool):
    """保存用户+assistant消息，读回验证"""
    conversation_id = str(uuid.uuid4())

    user_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": "user",
        "content": "你好，今天天气怎么样？",
        "toolCalls": [],
        "status": "done",
        "agentId": "test-agent",
    }
    await save_message(pool, user_msg)

    assistant_msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": "今天天气晴朗，适合出行。",
        "toolCalls": [],
        "status": "done",
        "agentId": "test-agent",
    }
    await save_message(pool, assistant_msg)

    messages = await get_messages_by_conversation(pool, conversation_id)

    assert len(messages) == 2, f"期望 2 条，实际 {len(messages)}"
    assert messages[0]["role"] == "user", f"第一条不是 user: {messages[0]['role']}"
    assert messages[1]["role"] == "assistant", f"第二条不是 assistant: {messages[1]['role']}"
    assert messages[0]["content"] == "你好，今天天气怎么样？"
    assert messages[1]["content"] == "今天天气晴朗，适合出行。"

    print(f"  PASS: save → retrieve ({len(messages)} 条消息，顺序正确)")
    return True


async def test_multi_turn(pool: AsyncConnectionPool):
    """多轮对话测试"""
    conversation_id = str(uuid.uuid4())  # 多轮对话

    turns = [
        ("user", "Hello"),
        ("assistant", "Hi! How can I help?"),
        ("user", "Tell me a joke"),
        ("assistant", "Why did the chicken cross the road?"),
        ("user", "Another one"),
        ("assistant", "What do you call a fish with no eyes? Fsh!"),
    ]

    for role, content in turns:
        await save_message(pool, {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "toolCalls": [],
            "status": "done",
            "agentId": "test-agent",
        })

    messages = await get_messages_by_conversation(pool, conversation_id)
    assert len(messages) == 6, f"期望 6 条，实际 {len(messages)}"

    for i, (expected_role, expected_content) in enumerate(turns):
        assert messages[i]["role"] == expected_role, \
            f"[{i}] role={messages[i]['role']} (期望 {expected_role})"
        assert messages[i]["content"] == expected_content

    # 验证交替模式
    for i in range(len(messages)):
        expected_role = "user" if i % 2 == 0 else "assistant"
        assert messages[i]["role"] == expected_role, \
            f"[{i}] 交替模式失败: role={messages[i]['role']}"

    print(f"  PASS: {len(turns)} 轮对话，顺序和内容正确")
    return True


async def test_empty_conversation(pool: AsyncConnectionPool):
    """空对话查询不报错"""
    messages = await get_messages_by_conversation(pool, str(uuid.uuid4()))
    assert messages == []
    print("  PASS: 不存在的对话返回空列表")
    return True


async def test_conversation_isolation(pool: AsyncConnectionPool):
    """不同对话的消息不应混淆"""
    conv_a = str(uuid.uuid4())
    conv_b = str(uuid.uuid4())

    await save_message(pool, {
        "id": str(uuid.uuid4()), "conversation_id": conv_a,
        "role": "user", "content": "A's question", "toolCalls": [],
        "status": "done", "agentId": "test",
    })
    await save_message(pool, {
        "id": str(uuid.uuid4()), "conversation_id": conv_b,
        "role": "user", "content": "B's question", "toolCalls": [],
        "status": "done", "agentId": "test",
    })

    msgs_a = await get_messages_by_conversation(pool, conv_a)
    msgs_b = await get_messages_by_conversation(pool, conv_b)

    assert len(msgs_a) == 1 and msgs_a[0]["content"] == "A's question"
    assert len(msgs_b) == 1 and msgs_b[0]["content"] == "B's question"
    print("  PASS: 对话隔离正确")
    return True


async def main():
    print("=" * 60)
    print("chat_messages 端到端读写测试")
    print(f"数据库: {settings.postgres_uri}")
    print("=" * 60)

    # 初始化独立 pool
    try:
        pool = AsyncConnectionPool(
            conninfo=settings.postgres_uri,
            min_size=1,
            max_size=3,
            kwargs={"autocommit": True, "prepare_threshold": 0},
        )
        print("✓ 数据库连接池已创建")
    except Exception as e:
        print(f"FAIL: 无法连接数据库: {e}")
        return False

    try:
        await ensure_table(pool)

        results = []

        print("\n[1/4] 单轮对话测试")
        results.append(await test_save_and_retrieve(pool))

        print("\n[2/4] 多轮对话测试")
        results.append(await test_multi_turn(pool))

        print("\n[3/4] 空对话查询")
        results.append(await test_empty_conversation(pool))

        print("\n[4/4] 对话隔离测试")
        results.append(await test_conversation_isolation(pool))

        print("\n" + "=" * 60)
        passed = sum(1 for r in results if r)
        total = len(results)
        print(f"结果: {passed}/{total} 通过")
        for i, r in enumerate(results):
            status = "PASS" if r else "FAIL"
            names = ["单轮读写", "多轮对话", "空对话", "对话隔离"]
            print(f"  [{status}] {names[i]}")
        print("=" * 60)
        return passed == total
    finally:
        await pool.close()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
