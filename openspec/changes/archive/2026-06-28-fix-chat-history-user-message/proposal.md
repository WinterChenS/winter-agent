# Proposal: 修复聊天历史未记录用户问题

## 问题描述

用户在使用 AI Chat 功能发送消息后刷新页面，聊天历史中只显示 AI 的回复，不显示用户自己的提问。

## 根因分析

在 `ai_service/api/routes/chat.py` 的 `stream_generate()` 函数中（第 314-330 行），仅在流式响应完成后将 assistant 消息持久化到 `chat_messages` 表：

```python
message_dict = {
    "role": "assistant",  # 硬编码为 assistant
    ...
}
asyncio.create_task(save_message(pool, message_dict))
```

用户的提问 (`request.message`) 虽然被传入 LangGraph 的 `HumanMessage`（第 203 行），但从未被持久化。`save_message` 函数本身支持任意 role，只是调用方没有传 `role: "user"`。

## 修复目标

在 `stream_generate()` 中，处理开始时同步将用户消息持久化到 `chat_messages` 表，确保聊天历史完整记录问答对。
