# Comet Design Handoff

- Change: user-conversation-persistence
- Phase: design
- Mode: compact
- Context hash: 91e403499ebf904975260fc7b717c2b551ff8bb5bb6e1204539fdbdbaee4caa5

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/user-conversation-persistence/proposal.md

- Source: openspec/changes/user-conversation-persistence/proposal.md
- Lines: 1-30
- SHA256: 828518407898f98f5fd39c0ce16b5e345f4a2430a6f7a2501254de8962d692ad

```md
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
```

## openspec/changes/user-conversation-persistence/design.md

- Source: openspec/changes/user-conversation-persistence/design.md
- Lines: 1-58
- SHA256: e9942f88eea3fb30bb7c408e2e3ee7971cbd682ef1485dcd0c82306dbb5aca1e

```md
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
```

## openspec/changes/user-conversation-persistence/tasks.md

- Source: openspec/changes/user-conversation-persistence/tasks.md
- Lines: 1-27
- SHA256: ba6206e527f5fbbaab3839904a0ebd22f3571280877f6dde2c5d2d1152b96a56

```md
## 1. 数据库 Migration

- [ ] 1.1 创建 `conversations` 表 migration SQL
- [ ] 1.2 创建 `chat_messages` 增加 `username` 字段的 migration SQL

## 2. Backend — Repository 层

- [ ] 2.1 新增 `conversation_repository.py`：create_conversation、get_conversations_by_username、delete_conversation
- [ ] 2.2 修改 `chat_message_repository.py`：save_message 增加 username 参数，get_messages_by_conversation 增加 username 校验

## 3. Backend — API 层

- [ ] 3.1 新增会话 CRUD 路由：GET/POST/DELETE `/api/chat/conversations`
- [ ] 3.2 修改 `stream_generate`：消息持久化时写入 username（从 X-User header 提取）
- [ ] 3.3 修改 history 接口：查询时校验 username 归属

## 4. Frontend 适配

- [ ] 4.1 修改 `useSessions.ts`：替换 localStorage 为 API 调用
- [ ] 4.2 修改 `ChatInterface.tsx`：适配新的会话加载流程（首次加载从 API 获取列表）
- [ ] 4.3 修改 `Sidebar.tsx`：适配服务端返回的会话数据结构

## 5. 验证

- [ ] 5.1 运行后端测试确认无回归
- [ ] 5.2 构建前端确认无编译错误
- [ ] 5.3 端到端测试：创建会话 → 发送消息 → 刷新 → 历史保留 → 删除会话
```

