## Context

前端当前仅有旧版 table 风格 AdminAgents 页面和简单 session-list 侧边栏。后端 `agent-backend-proxy` 已提供 8 个 REST 端点（CRUD + enable/disable/clone），前端可直接调用。

## Goals / Non-Goals

**Goals:**
- 侧边栏升级为 ChatGPT 风格固定导航 + Recent Chats
- Agent 管理页替换为 Card 布局 + Drawer 编辑器
- Prompt 编辑器使用 CodeMirror 6
- 聊天页面实时展示 Agent 状态

**Non-Goals:**
- 不修改后端（Python/SpringBoot）
- 不修改数据库
- 不修改 SSE 协议
- 不做 MCP/Tools/Knowledge 等预留功能的实际实现

## Decisions

### Decision 1: 保留现有路由结构
**选择**: 新增 `/agents` 路由替换 `/admin/agents`，保留 `/` 和 `/chat/:id` 不变
**理由**: 最小化路由变更，不影响已有聊天功能

### Decision 2: 前端数据获取
**选择**: 使用自定义 `useAgent` composable hook + `fetch()` API，与现有模式一致（无 axios、无 React Query）
**理由**: 保持项目代码风格统一

### Decision 3: Drawer 实现
**选择**: 纯 Tailwind CSS 实现 Drawer（fixed right-0 + translate-x + 遮罩），无额外依赖
**理由**: 项目无组件库，用 Tailwind 可保持轻量；类似 ChatGPT 的侧边栏动画逻辑

### Decision 4: 模型配置安全
**选择**: `model_config` 字段通过 SpringBoot `GET /api/agents` 正常返回（不含敏感凭证），前端 Drawer 中直接编辑 `temperature`/`top_p`/`max_tokens`/`model_name` 等字段，写入 `model_config` JSONB
**理由**: 真正的 API key 存储在服务端 `.env`，model_config 不含敏感信息

### Decision 5: Agent 状态展示
**选择**: 扩展 Zustand store 的 `activeAgent`/`agentStatus` 字段，在 Chat Header 中展示
**理由**: 已有 agent.started/agent.finished SSE 事件处理，只需 UI 渲染

## Risks / Trade-offs

- **[Risk] React 项目用 `.vue` 文件** → 已纠正，全部使用 `.tsx`
- **[Risk] CodeMirror 6 bundle size** → 支持 Tree-shaking，按需导入语言包
- **[Risk] 侧边栏 Session 分组性能** → 使用 `useMemo` 缓存分组结果
