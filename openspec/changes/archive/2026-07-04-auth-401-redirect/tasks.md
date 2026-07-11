## 1. 创建全局 apiFetch

- [x] 1.1 在 `frontend/src/services/api.ts` 新增 `apiFetch` 函数，拦截 401 自动跳转 `/login`
- [x] 1.2 替换 `frontend/src/services/api.ts` 中的 fetch 调用为 `apiFetch`
- [x] 1.3 替换 `frontend/src/features/ai-chat/services/chatApi.ts` 中的 fetch
- [x] 1.4 替换 `frontend/src/features/ai-chat/services/agent.ts` 中的 fetch
- [x] 1.5 替换 `frontend/src/hooks/useChat.ts` 中的 fetch
- [x] 1.6 替换 `frontend/src/hooks/useStream.ts` 中的 fetch

## 2. 验证

- [x] 2.1 构建前端确认无编译错误
