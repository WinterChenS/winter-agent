# Comet Design Handoff

- Change: message-copy
- Phase: design
- Mode: compact
- Context hash: f5500ae15e832a4b34c134dfa4be987769d02c1502b379864e9881391446bf1c

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/message-copy/proposal.md

- Source: openspec/changes/message-copy/proposal.md
- Lines: 1-13
- SHA256: 7dbf4eba9f8e60356ec1e73562e295d201514c0bdabd103de1dd66378cdc5c52

```md
# Proposal: 聊天消息复制功能

## Why

当前聊天页面缺少消息复制能力。用户无法方便地复制 AI 生成的 Markdown 内容（代码块、表格、图片链接等）到其他工具（Typora、Obsidian、VS Code）使用。需要参考 ChatGPT 的交互体验，在每条消息上提供一键复制按钮。

## What Changes

- 新增 `copyText` 工具函数（优先 clipboard API，降级 execCommand）
- 新增 `MessageActions` 组件（hover 显示复制按钮，点击后显示 Copied 反馈）
- Message 数据结构增加 `rawContent` 字段，存储原始 Markdown 文本
- 在 `MessageBubble` 中集成 `MessageActions`
- 用户消息复制原始输入文本，AI 消息复制原始 Markdown
```

## openspec/changes/message-copy/design.md

- Source: openspec/changes/message-copy/design.md
- Lines: 1-3
- SHA256: 1b88c5cd8258cf9b4b6783dc9bd15f6323f85950fc722cbc9b76042544ba9c31

```md
# Design: 聊天消息复制功能

> 详细设计将由 brainstorming 阶段产出。
```

## openspec/changes/message-copy/tasks.md

- Source: openspec/changes/message-copy/tasks.md
- Lines: 1-10
- SHA256: c7aeedff5eadefa0933cc09a38792571b81f9a45da5418e87cf3ddae1d83f62d

```md
# Tasks: 聊天消息复制功能

## 任务

- [ ] **Task 1**: 新增 `utils/copy.ts` — copyText 工具函数
- [ ] **Task 2**: Message 类型增加 `rawContent` 字段
- [ ] **Task 3**: 新增 `MessageActions` 组件（hover 显示复制按钮，Copied 反馈）
- [ ] **Task 4**: `MessageBubble` 集成 MessageActions
- [ ] **Task 5**: `useChatStream` 传递 rawContent（用户原始输入 + AI Markdown 原始内容）
- [ ] **Task 6**: 测试验证（vitest + 手动验证）
```

