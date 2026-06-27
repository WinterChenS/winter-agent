# Tasks: 修复聊天历史未记录用户问题

## 任务

- [x] **Task 1**: 在 `ai_service/api/routes/chat.py` 的 `stream_generate()` 中添加用户消息持久化逻辑
  - 位置：graph_runner 和 bus_runner 创建后，流处理循环前
  - 调用 `save_message` 保存 `role: "user"` 的消息至 `chat_messages` 表
  - 使用 `asyncio.create_task` 异步执行，不阻塞主流程
