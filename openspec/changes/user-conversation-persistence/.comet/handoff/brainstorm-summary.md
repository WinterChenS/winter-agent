# Brainstorm Summary

- Change: user-conversation-persistence
- Date: 2026-07-04

## 确认的技术方案

1. **DB**: 新建 `conversations` 表 (id, username, title, created_at, updated_at)；`chat_messages` 加 `username` 列 + 索引
2. **级联删除**: 应用层事务包裹，先删 messages 再删 conversation，不设 DB CASCADE
3. **X-User 提取**: `request.headers.get("X-User", "system")` 兜底
4. **Repository**: `conversation_repository.py` — create/get_by_username/delete/update_title
5. **API**: GET/POST/DELETE `/api/chat/conversations`
6. **消息写入**: stream_generate 中从 X-User 提取 username 写入 chat_messages
7. **前端**: localStorage → API 调用，首次加载自动创建默认会话，conversationId 由服务端生成
8. **Sidebar**: API 返回数据兼容现有 Conversation 接口

## 关键取舍与风险

- username 关联 vs user_id：用 username 避免跨系统查 ID，X-User header 已有
- 历史数据兼容：已有消息 username 为 NULL，查询不做强制校验
- 事务一致性：delete 操作用事务保证原子性

## 测试策略

- Migration 执行验证
- Repository 单元测试 (CRUD + 级联删除)
- API 集成测试 (不同 X-User 隔离)
- Frontend 构建 + 端到端测试

## Spec Patch

无
