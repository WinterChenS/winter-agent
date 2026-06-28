# Brainstorm Summary

- Change: agent-management-ui
- Date: 2026-06-28

## 确认的技术方案

**侧边栏**: 新 `Sidebar.tsx`，从后端 API 获取数据（agents + chat history）。顶部固定导航（sticky），底部 Recent Chats 按 Today/Yesterday 分组（useMemo），仅聊天列表滚动。替换旧 Sidebar 集成到 ChatInterface。预留 Tools/Knowledge/MCP/Settings 菜单项（locked 样式）。

**Agent 管理**: `useAgent` composable（fetch + useState/useEffect）→ `AgentCard` 组件。客户端搜索/排序/分页。Drawer 使用 Tailwind fixed + translate-x + transition + 遮罩。CodeMirror 6 按需导入 4 个包。

**Agent 状态**: 扩展现有 Zustand store 的 activeAgent/agentStatus 字段在 Chat Header 中渲染。SSE 事件处理已就绪。

**测试策略**: vitest 组件测试 + API hook 测试。

## 关键取舍与风险

- 客户端过滤适用于少量 agent（当前 < 100），未来量大时切换服务端分页
- CodeMirror 6 tree-shaking 只导入 markdown 语言包
- 所有 UI 组件纯 Tailwind 无额外依赖

## Spec Patch

无
