---
change: message-copy
design-doc: docs/superpowers/specs/2026-06-28-message-copy-design.md
base-ref: 233c8f3debee56414bc64bd5a48314425e8cf6c8
archived-with: 2026-06-28-message-copy
---

# 聊天消息复制功能实现计划

## Tasks

- [x] **Task 1**: 创建 utils/copy.ts — copyText 工具函数
- [x] **Task 2**: Message 类型增加 rawContent 字段
- [x] **Task 3**: chatStore completeMessage 自动设置 rawContent
- [x] **Task 4**: 新增 MessageActions 组件（hover 显隐 + Copied 反馈）
- [x] **Task 5**: MessageBubble 集成 MessageActions
- [x] **Task 6**: useChatStream 传递 rawContent
- [x] **Task 7**: 单元测试（copyText + rawContent）
- [x] **Task 8**: 最终验证（build + tests）
- [x] **Task 9**: 手动验证
