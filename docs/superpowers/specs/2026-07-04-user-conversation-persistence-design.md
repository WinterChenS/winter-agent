---
comet_change: user-conversation-persistence
role: technical-design
canonical_spec: openspec
---

# User Conversation Persistence — Technical Design

## Context

会话列表存于 localStorage，`chat_messages` 无用户标识。Spring Boot BFF 已将 `username` 通过 `X-User` header 转发到 FastAPI。本次改造将会话和消息按用户维度持久化到 PostgreSQL。

## Architecture

```
前端                          FastAPI                         PostgreSQL
──                           ───────                         ──────────
GET  /conversations    →     提取 X-User →                   conversations
POST /conversations    →     WHERE username=? →              (id, username, title,
DELETE /conversations  →     DELETE + 事务                    created_at, updated_at)
                                                                 │
stream_generate        →     提取 X-User →                   chat_messages
                              INSERT(username)               (+username, idx)
```

## Database

### conversations 表

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL DEFAULT '新对话',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_conv_username ON conversations(username, updated_at DESC);
```

### chat_messages 加 username

```sql
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS username VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_msg_username_conv
    ON chat_messages(username, conversation_id);
```

### 级联删除

用事务包裹：先删除 messages，再删除 conversation。

## Backend

### X-User 提取

```python
from fastapi import Request
def _get_username(request: Request) -> str:
    return request.headers.get("X-User", "system")
```

### conversation_repository.py

- `create_conversation(conn, username, title)` → dict
- `get_conversations_by_username(conn, username)` → list[dict]
- `delete_conversation(conn, conv_id, username)` → bool (事务内级联删除消息)
- `update_conversation_title(conn, conv_id, username, title)` → bool

### API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/chat/conversations` | 按 updated_at DESC 返回用户会话列表 |
| POST | `/api/chat/conversations` | body: `{title?}`，返回会话对象 |
| DELETE | `/api/chat/conversations/{id}` | 级联删除，返回 `{ok: true}` |

### 消息写入

`stream_generate` 中消息持久化时从 `X-User` 提取 username，写入 `chat_messages.username`。

## Frontend

### API 客户端（`services/api.ts`）

```typescript
getConversations(): Promise<Conversation[]>
createConversation(title?: string): Promise<Conversation>
deleteConversation(id: string): Promise<void>
```

### useSessions 改造

localStorage → API 调用。useEffect 首次加载调 GET，新建/删除调 POST/DELETE。conversationId 由服务端生成。

### ChatInterface

首次加载无会话时自动创建默认会话。切换/新建/删除均通过 API。

### Sidebar

API 返回数据兼容现有 `Conversation` 接口和 `SessionGroup` 渲染。

## Testing Strategy

- DB: 验证 migration 执行、索引创建
- Repository: 单元测试 CRUD、级联删除、事务回滚
- API: 集成测试 — 不同 X-User 返回不同会话、删除会话清理消息
- Frontend: 构建验证、端到端创建/切换/删除会话
