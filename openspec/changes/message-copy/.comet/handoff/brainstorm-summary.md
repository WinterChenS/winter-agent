# Brainstorm Summary

- Change: message-copy
- Date: 2026-06-28

## 确认的技术方案

1. `utils/copy.ts` — copyText 函数，clipboard API 优先，execCommand 降级
2. `Message.rawContent` — 存储原始 Markdown/用户输入
3. `MessageActions` 组件 — hover 显示复制按钮，点击显示 ✓ Copied 2s
4. `MessageBubble` 集成 MessageActions

## 关键取舍与风险

- rawContent 存 Message 对象内聚，不单独 map
- AI rawContent 从 SSE delta 累计值获取，天然保留 Markdown 原文
- 不修改现有消息渲染逻辑

## 测试策略

- vitest 测试 copyText 降级
- 手动验证粘贴到 Typora/VS Code

## Spec Patch

无
