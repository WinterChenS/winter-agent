# Brainstorm Summary

- Change: optimize-chat-layout
- Date: 2026-06-28

## 确认的技术方案

方案 A：新建 `ChatContainer` 组件，包裹消息区和输入区，统一约束 `max-w-[820px] mx-auto`。

- 新建 `ChatContainer.tsx`（纯布局，无业务逻辑）
- `ChatInterface.tsx`：main 和 footer 各包一层 ChatContainer
- `MessageList.tsx`：去掉自身 px-4（移入 ChatContainer）
- `MessageBubble.tsx`：`max-w-[80%]` → `max-w-[85%]`

### 响应式
- <768px: px-4, 100% width
- 768-1200px: px-6, up to 820px
- >1200px: px-8, fixed 820px centered

## 关键取舍与风险

- 侧边栏保持贴左，不参与居中约束
- Header 保持全宽
- 不改 Tailwind 配置，使用任意值 `max-w-[820px]`
- 不碰消息渲染逻辑、SSE 处理、store

## 测试策略

- 视觉验证：1920px / 1440px / 1024px / 768px / 375px
- 功能验证：发送消息、流式输出、历史加载
- 现有 vitest 测试通过

## Spec Patch

无
