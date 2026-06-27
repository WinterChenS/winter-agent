# Design: 修复聊天历史未记录用户问题

## 修复方案

在 `stream_generate()` 中，流式处理开始前（graph_runner 启动后），同步将用户消息写入 `chat_messages` 表。

### 改动文件

`ai_service/api/routes/chat.py` — 在 `stream_generate()` 中新增用户消息持久化逻辑。

### 改动位置

在 graph_runner 和 bus_runner 创建任务后（约第 275 行之后），添加用户消息的 `save_message` 调用：

```python
# Persist user message
try:
    pool_user = get_pool()
    if pool_user:
        from db.chat_message_repository import save_message as save_msg
        user_message_id = str(uuid.uuid4())
        user_msg_dict = {
            "id": user_message_id,
            "conversation_id": trace_ctx.conversation_id,
            "role": "user",
            "content": request.message,
            "toolCalls": [],
            "status": "done",
            "agentId": active_agent,
        }
        asyncio.create_task(save_msg(pool_user, user_msg_dict))
except (ImportError, Exception):
    pass
```

### 设计决策

- **在流开始前保存**：用户消息内容固定，无需等待响应，立即异步写入不影响流式延迟
- **复用已有函数**：`save_message` 已支持任意 role，无需修改 repository 层
- **异步写入**：使用 `asyncio.create_task` 避免阻塞主流程
- **错误隔离**：持久化失败不影响用户体验
