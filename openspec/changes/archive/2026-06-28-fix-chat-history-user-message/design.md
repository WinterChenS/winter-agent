# Design: 修复聊天历史未记录用户问题

## 修复方案

在 `stream_generate()` 中，if/else 分支（mock 模式 / plan-execute-compose 模式）之前，将用户消息写入 `chat_messages` 表。

### 改动文件

`ai_service/api/routes/chat.py` — 在 `stream_generate()` 中新增用户消息持久化逻辑。

### 改动位置

在 try 块入口、if/else 分支之前（event_ctx 初始化后），添加用户消息的 `save_message` 调用。该位置覆盖 mock 模式（无 API key）和真实模式（plan-execute-compose graph）两条路径。

### 设计决策

- **在 if/else 分支前保存**：确保 mock 模式和真实模式都能持久化用户提问
- **异步写入**：使用 `asyncio.create_task` 避免阻塞主流程
- **错误隔离**：持久化失败不影响用户体验
