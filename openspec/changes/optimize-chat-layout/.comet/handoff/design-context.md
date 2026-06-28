# Comet Design Handoff

- Change: optimize-chat-layout
- Phase: design
- Mode: compact
- Context hash: 8ecdde25fcc2fcc435a1d2f52c5b13351dbb546f16d1df0dd556357afe638da1

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/optimize-chat-layout/proposal.md

- Source: openspec/changes/optimize-chat-layout/proposal.md
- Lines: 1-12
- SHA256: 247c246b67c985a9f66aa4b2b80c47133845de176cb4b7da132ebcf8e6cb59a1

```md
# Proposal: 优化聊天页面布局

## Why

当前聊天页面采用全宽布局，消息内容左右贴边显示，在大屏幕上阅读体验差。需要参考 ChatGPT 的居中布局风格，限制内容最大宽度，增加留白，提升阅读体验。

## What Changes

- 聊天内容区域居中显示，限制最大宽度 (~820px)
- Header、消息列表、输入框统一使用相同宽度约束
- 添加响应式断点支持（>1200px / 768-1200px / <768px）
- 保持现有组件逻辑不变，仅调整 Layout 和 CSS
```

## openspec/changes/optimize-chat-layout/design.md

- Source: openspec/changes/optimize-chat-layout/design.md
- Lines: 1-3
- SHA256: a511b3eb11d38a50fe356d80a65959699ca8ab5a0ef3dd4b8ec78b67b82f2a05

```md
# Design: 优化聊天页面布局

> 详细设计将由 `/comet-design` brainstorming 阶段产出。
```

## openspec/changes/optimize-chat-layout/tasks.md

- Source: openspec/changes/optimize-chat-layout/tasks.md
- Lines: 1-9
- SHA256: 1b12cc7709febbe20bc077cd0c7ba52d897ec0f8ef0317c07c279061614bacbc

```md
# Tasks: 优化聊天页面布局

## 任务

- [ ] **Task 1**: 创建居中布局容器组件（ChatContainer），限制最大宽度 820px
- [ ] **Task 2**: 调整 MessageList 和 MessageBubble 适配居中宽度
- [ ] **Task 3**: 调整 InputBox 与消息区域宽度对齐
- [ ] **Task 4**: 调整 Header 与聊天区域宽度对齐
- [ ] **Task 5**: 添加响应式断点样式
```

