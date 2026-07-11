## Why

会话列表目前存储在浏览器 localStorage 中，`chat_messages` 表没有用户标识，无法按用户维度管理历史会话。需要将会话管理迁移到数据库，按用户维度存储和查询。

## What Changes

- **DB**: 新建 `conversations` 表（id, username, title, created_at）
- **DB**: `chat_messages` 增加 `username` 字段 + 索引
- **API**: 新增会话 CRUD：`GET/POST/DELETE /api/chat/conversations`
- **API**: 消息存储和查询 API 增加 username 过滤
- **Frontend**: 删除 localStorage 会话存储，侧栏调 API 展示/新建/删除会话
- **BFF**: 不改动（已有 `X-User` header 转发）

## Capabilities

### New Capabilities

- `user-conversation-persistence`: 按用户维度的会话持久化存储和 CRUD

### Modified Capabilities

<!-- 不修改已有 capability spec -->

## Impact

- `ai_service/db/` — 新增 migration SQL，修改 `chat_message_repository.py`
- `ai_service/api/routes/chat.py` — 新增会话 CRUD 路由，修改消息存储/查询
- `frontend/src/hooks/useSessions.ts` — 替换为 API 调用
- `frontend/src/pages/ChatInterface.tsx` — 适配新的会话 API
- `frontend/src/components/Sidebar.tsx` — 适配新的会话数据结构
