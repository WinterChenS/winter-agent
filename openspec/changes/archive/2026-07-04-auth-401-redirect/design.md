## Context

当前前端没有全局 401 处理机制。每次 `fetch` 调用手动检查 `response.ok`，但不对 401 做特殊处理。浏览器在收到带 `WWW-Authenticate` 头的 401 响应时会弹出原生 Basic Auth 对话框。

## Fix

创建 `apiFetch` 包装函数，在原生 `fetch` 基础上自动处理 401：

1. 发起请求
2. 若 `response.status === 401`：清除 `localStorage` 中的 token，触发 logout，跳转 `/login`
3. 否则正常返回 response

然后逐一替换所有 API 调用点为 `apiFetch`。
