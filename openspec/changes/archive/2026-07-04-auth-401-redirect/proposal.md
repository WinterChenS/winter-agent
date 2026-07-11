## Why

登录 token 过期或失效后，浏览器弹出原生 HTTP Basic Auth 对话框要求输入账号密码，而不是跳转到登录页面。需要在任何 API 调用返回 401 时自动清除认证状态并重定向到 `/login`。

## What Changes

- **前端**: 创建全局 fetch 包装器，拦截所有 401 响应，清除 token 并跳转 `/login`
- **前端**: 替换所有直接调用 `fetch` 的地方为包装后的 fetch
- **后端**: 确保 401 响应不包含 `WWW-Authenticate: Basic` 头（避免触发浏览器原生弹窗）

## Impact

- `frontend/src/services/api.ts` — 添加 401 拦截
- `frontend/src/features/ai-chat/services/chatApi.ts` — 使用统一 fetch
- `frontend/src/features/ai-chat/services/agent.ts` — 使用统一 fetch
- `frontend/src/hooks/useChat.ts` — 使用统一 fetch
- `frontend/src/hooks/useStream.ts` — 添加 401 处理
- `frontend/src/pages/LoginPage.tsx` — 不需要改动
