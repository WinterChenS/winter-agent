## Context

会话列表当前存于 localStorage，`chat_messages` 按 `conversation_id` 查询，无用户隔离。Spring Boot BFF 已将认证用户名通过 `X-User` header 转发到 FastAPI。

## Architecture

```
前端                   FastAPI                    PostgreSQL
──                    ───────                    ─────────
POST /conversations →  提取 X-User →            conversations (id, username, title, ...)
GET  /conversations →  WHERE username = ? →      chat_messages (+username, idx)
DEL  /conversations →  DELETE + 级联清理消息
```

## Decisions

### D1: 用户标识使用 username 而非 user_id

Spring Boot BFF 的 JWT subject 是 username，`X-User` header 传递的也是 username。使用 username 作为关联字段避免跨系统查 user_id，且 sys_user.username 有唯一约束。

### D2: conversations 表结构

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL,
    title VARCHAR(200) DEFAULT '新对话',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_conversations_username ON conversations(username, updated_at DESC);
```

### D3: chat_messages 加 username 和索引

```sql
ALTER TABLE chat_messages ADD COLUMN username VARCHAR(50);
CREATE INDEX idx_messages_username_conv ON chat_messages(username, conversation_id);
```

### D4: 会话 API 设计

- `GET /api/chat/conversations` — 从 X-User 获取 username，返回该用户的会话列表（按 updated_at DESC）
- `POST /api/chat/conversations` — 创建新会话，title 可选（默认"新对话"）
- `DELETE /api/chat/conversations/{id}` — 删除会话 + 级联删除关联消息

### D5: 前端适配

- 替换 `useSessions` hook 中的 localStorage 操作为 API 调用
- 侧栏加载时调 `GET /conversations`，新建/删除调对应 API
- `chatApi.ts` 中消息发送时无需改动（已有 conversationId）
- 历史加载接口 `GET /api/chat/history/{id}` 增加 username 校验

## Risks

- **[X-User 缺失]** 若 BFF 未转发 header，默认 username 为 "system" → 保持向后兼容
- **[级联删除]** 删除会话时需同时删除 messages，使用事务保证一致性
- **[迁移兼容]** 已有 chat_messages 数据中 username 为 NULL → 查询时使用 `IS NOT DISTINCT FROM` 或给历史数据批量补填
