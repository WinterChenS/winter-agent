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
