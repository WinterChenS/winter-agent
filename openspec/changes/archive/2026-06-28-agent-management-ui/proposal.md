## Why

当前侧边栏仅有聊天历史列表，缺少结构化导航。Agent 管理页面是旧版 table 风格，体验差。聊天页面缺少当前 Agent 的实时状态展示。前端需要升级为 ChatGPT 风格的企业级 AI Agent 管理体验。

## What Changes

- **侧边栏**: 顶部固定导航（AI Studio / New Chat / Agents）+ 底部 Recent Chats（Today/Yesterday 分组），仅聊天列表滚动
- **Agent 管理页**: 替换 /admin/agents 为 Card 布局，支持搜索/分页/排序/启停，Hover 动效
- **Agent 编辑器**: Drawer 打开，分组展示 Basic/Prompt(CodeMirror 6)/Model/Tools/Trigger/Advanced
- **聊天 Agent 状态**: 聊天顶部实时显示当前 Agent 图标+名称，基于 SSE 事件驱动
- **安全**: model_config 通过后端接口安全获取，前端不处理敏感凭证
- **CodeMirror 6**: 作为 Prompt 编辑器，支持 Markdown、复制、自动换行、全屏

## Capabilities

### New Capabilities
- `sidebar-navigation`: ChatGPT 风格侧边栏导航（固定顶部分组 + Recent Chats 滚动）
- `agent-management-page`: Agent 管理页面（Card 布局 + 搜索/分页/排序 + Drawer 编辑器）
- `prompt-editor`: CodeMirror 6 系统提示词编辑器组件

### Modified Capabilities
- `ai-chat-ui`: 新增侧边栏导航需求 + 聊天 Agent 状态实时展示需求

## Impact

- `frontend/src/components/Sidebar.tsx` — 重写为 ChatGPT 风格导航
- `frontend/src/pages/AdminAgents.tsx` — 删除，替换为 AgentManagement 页面
- `frontend/src/pages/ChatInterface.tsx` — 集成新 Sidebar + Agent 状态展示
- `frontend/src/features/ai-chat/` — 新增 Agent 状态相关 store 字段
- `frontend/src/views/AgentManagement/` — 新增
- `frontend/src/components/AgentCard.vue` — 应为 .tsx（React）
- `frontend/package.json` — 新增 codemirror 依赖
