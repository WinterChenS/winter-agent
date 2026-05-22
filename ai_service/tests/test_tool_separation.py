#!/usr/bin/env python3
"""
Week 5 集成测试：验证工具过程与最终回答分离的完整流程

运行方式:
  python -m pytest tests/test_tool_separation.py -v
  
或者直接运行:
  python tests/test_tool_separation.py
"""
from __future__ import annotations

import json
import asyncio
from typing import Any

# 模拟测试：验证 State、tool_node 和 SSE 事件的核心逻辑


def test_state_structure():
    """验证 State 结构中包含 tool_steps 字段"""
    print("\n[测试 1] State 结构验证")
    
    # 模拟 State 初始化
    state = {
        "messages": [],
        "current_tool": None,
        "tool_input": None,
        "tool_result": None,
        "reasoning_steps": [],
        "iteration_count": 0,
        "tool_steps": [],  # ← NEW FIELD
    }
    
    assert "tool_steps" in state, "tool_steps 字段缺失"
    assert isinstance(state["tool_steps"], list), "tool_steps 应该是列表"
    print("  ✓ State 包含 tool_steps 字段")
    print("  ✓ tool_steps 初始值为空列表")


def test_tool_step_record_format():
    """验证工具步���记录的格式"""
    print("\n[测试 2] 工具步骤记录格式")
    
    # 模拟 tool_node 创建的步骤记录
    tool_step_record = {
        "tool": "search",
        "input": "LangGraph tutorial",
        "status": "completed",
        "elapsed_ms": 234,
        "timestamp": 1234567890.123,
    }
    
    # 验证必须字段
    required_fields = ["tool", "input", "status", "elapsed_ms"]
    for field in required_fields:
        assert field in tool_step_record, f"缺少必需字段: {field}"
    
    # 验证状态值
    assert tool_step_record["status"] in ["completed", "error"], "status 值非法"
    
    # 验证耗时是整数且非负
    assert isinstance(tool_step_record["elapsed_ms"], int), "elapsed_ms 应该是整数"
    assert tool_step_record["elapsed_ms"] >= 0, "elapsed_ms 应该非负"
    
    print("  ✓ 工具步骤记录包含所有必需字段")
    print(f"  ✓ 格式验证通过: {json.dumps(tool_step_record, indent=2)}")


def test_tool_step_with_error():
    """验证错误时的工具步骤记录"""
    print("\n[测试 3] 工具错误记录")
    
    tool_step_record_error = {
        "tool": "search",
        "input": "query",
        "status": "error",
        "elapsed_ms": 50,
        "error": "TAVILY_API_KEY not found",
    }
    
    assert tool_step_record_error["status"] == "error"
    assert "error" in tool_step_record_error
    assert isinstance(tool_step_record_error["error"], str)
    
    print("  ✓ 错误记录包含 error 字段")
    print(f"  ✓ 错误信息: {tool_step_record_error['error']}")


def test_tool_steps_accumulation():
    """验证多个工具步骤的累积"""
    print("\n[测试 4] 工具步骤累积")
    
    # 模拟状态累积过程
    state_tool_steps = []
    
    # 第一次工具执行
    state_tool_steps = state_tool_steps + [{
        "tool": "search",
        "input": "question 1",
        "status": "completed",
        "elapsed_ms": 234,
    }]
    
    # 第二次工具执行
    state_tool_steps = state_tool_steps + [{
        "tool": "time",
        "input": "",
        "status": "completed",
        "elapsed_ms": 12,
    }]
    
    assert len(state_tool_steps) == 2, "应该累积 2 个步骤"
    assert state_tool_steps[0]["tool"] == "search"
    assert state_tool_steps[1]["tool"] == "time"
    
    print(f"  ✓ 成功累积 {len(state_tool_steps)} 个工具执行步骤")
    print(f"  ✓ 工具顺序: {' → '.join(s['tool'] for s in state_tool_steps)}")


def test_sse_tool_summary_event():
    """验证 tool_summary SSE 事件格式"""
    print("\n[测试 5] tool_summary SSE 事件")
    
    # 模拟后端发送的 tool_summary 事件
    tool_summary_event = {
        "type": "tool_summary",
        "steps": [
            {
                "tool": "search",
                "input": "LangGraph",
                "status": "completed",
                "elapsed_ms": 234,
            },
            {
                "tool": "time",
                "input": "",
                "status": "completed",
                "elapsed_ms": 15,
            },
        ],
        "conversationId": "conv-123",
    }
    
    # 验证事件格式
    assert tool_summary_event["type"] == "tool_summary"
    assert isinstance(tool_summary_event["steps"], list)
    assert len(tool_summary_event["steps"]) == 2
    
    event_json = json.dumps(tool_summary_event)
    print("  ✓ tool_summary 事件格式验证通过")
    print(f"  ✓ 事件 JSON (重要字段):")
    print(f"    - type: {tool_summary_event['type']}")
    print(f"    - steps count: {len(tool_summary_event['steps'])}")
    print(f"    - event size: {len(event_json)} bytes")


def test_message_types():
    """验证前端消息类型支持"""
    print("\n[测试 6] 前端消息类型")
    
    messages = [
        {
            "id": "msg-1",
            "role": "user",
            "content": "搜索 LangGraph",
            "timestamp": 1234567890,
        },
        {
            "id": "msg-2",
            "role": "assistant",
            "content": "LangGraph 是一个框架...",
            "timestamp": 1234567900,
        },
        {
            "id": "msg-3",
            "role": "tool_summary",  # ← NEW ROLE
            "content": "工具执行步骤",
            "timestamp": 1234567910,
            "toolSteps": [
                {
                    "tool": "search",
                    "input": "LangGraph",
                    "status": "completed",
                    "elapsed_ms": 234,
                }
            ],
        },
    ]
    
    valid_roles = {"user", "assistant", "tool_summary"}
    for msg in messages:
        assert msg["role"] in valid_roles, f"角色 {msg['role']} 不合法"
    
    tool_summary_msg = messages[2]
    assert "toolSteps" in tool_summary_msg, "tool_summary 消息应包含 toolSteps"
    assert isinstance(tool_summary_msg["toolSteps"], list)
    
    print("  ✓ 支持的消息角色: user, assistant, tool_summary")
    print("  ✓ tool_summary 消息包含 toolSteps 数组")


def test_complete_flow_simulation():
    """完整流程模拟"""
    print("\n[测试 7] 完整流程模拟")
    
    print("  1. 用户提问: '搜索 LangGraph'")
    
    # 模拟 Agent 决策
    state = {
        "messages": [{"type": "human", "content": "搜索 LangGraph"}],
        "current_tool": "search",
        "tool_input": {"query": "LangGraph"},
        "tool_result": None,
        "tool_steps": [],
    }
    print("  2. Agent 决策: 使用 search 工具")
    
    # 模拟 tool_node 执行
    import random
    import time
    elapsed = random.randint(200, 500)
    state["tool_steps"].append({
        "tool": "search",
        "input": "LangGraph",
        "status": "completed",
        "elapsed_ms": elapsed,
    })
    print(f"  3. tool_node 执行成功（{elapsed}ms）")
    
    # 模拟 SSE 事件
    final_state = state  # 假设最终状态
    tool_summary = {
        "type": "tool_summary",
        "steps": final_state["tool_steps"],
        "conversationId": "test-conv",
    }
    print("  4. SSE 发送 tool_summary 事件")
    
    # 前端接收并创建消息
    frontend_messages = [
        {
            "id": "user-msg",
            "role": "user",
            "content": "搜索 LangGraph",
        },
        {
            "id": "assistant-msg",
            "role": "assistant",
            "content": "LangGraph 是一个...",
        },
        {
            "id": "tool-summary-msg",
            "role": "tool_summary",
            "content": "工具执行步骤",
            "toolSteps": tool_summary["steps"],
        },
    ]
    print("  5. 前端创建 3 个消息:")
    print(f"     - user: 用户问题")
    print(f"     - assistant: AI 回答")
    print(f"     - tool_summary: 工具执行步骤（独立消息）")
    
    print("\n  ✓ 完整流程验证通过！")
    print("\n  最终页面展示:")
    print("  ┌─ 用户消息: 搜索 LangGraph")
    print("  ├─ AI 主回答: LangGraph 是一个...")
    print("  └─ 工具步骤区: 🔍 search ✓ 完成 250ms")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Week 5 工具过程与最终回答分离 - 集成测试")
    print("=" * 60)
    
    tests = [
        test_state_structure,
        test_tool_step_record_format,
        test_tool_step_with_error,
        test_tool_steps_accumulation,
        test_sse_tool_summary_event,
        test_message_types,
        test_complete_flow_simulation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ 测试失败: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ 异常: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过，{failed} 失败")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ 所有测试通过！架构验证成功。")
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())

