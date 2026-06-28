# Proposal: 聊天消息复制功能

## Why

当前聊天页面缺少消息复制能力。用户无法方便地复制 AI 生成的 Markdown 内容（代码块、表格、图片链接等）到其他工具（Typora、Obsidian、VS Code）使用。需要参考 ChatGPT 的交互体验，在每条消息上提供一键复制按钮。

## What Changes

- 新增 `copyText` 工具函数（优先 clipboard API，降级 execCommand）
- 新增 `MessageActions` 组件（hover 显示复制按钮，点击后显示 Copied 反馈）
- Message 数据结构增加 `rawContent` 字段，存储原始 Markdown 文本
- 在 `MessageBubble` 中集成 `MessageActions`
- 用户消息复制原始输入文本，AI 消息复制原始 Markdown
