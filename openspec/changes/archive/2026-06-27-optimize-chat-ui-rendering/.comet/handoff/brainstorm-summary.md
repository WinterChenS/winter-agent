# Brainstorm Summary

- Change: optimize-chat-ui-rendering
- Date: 2026-06-27

## 确认的技术方案

### A. SSE EventEnvelope 解析修复
- 在 `chatApi.ts` 的 `handleEvent` 入口统一从 `event.payload` 提取业务字段
- `const p = event.payload || event` 兼容 flat fallback
- `SseEvent` 类型更新为真实 EventEnvelope 结构（增加 `payload`、`schemaVersion` 等字段）
- Store 和组件接口不变

### B. IME 输入法守卫
- `InputBox.tsx` 使用 `useRef(isComposing)` + `compositionstart`/`compositionend` 事件
- `handleKeyDown` 顶部早返回：`isComposing.current === true` 时直接 return
- Safari 兼容通过 ref 拦截实现，不依赖 keyCode 判断

### C. Tool Execution Panel 聚合面板
- 重写 `ToolCallPanel.tsx`：Header（聚合状态图标 + 工具数量 + 折叠按钮）+ 可折叠 Body（ToolCallItem 列表）
- 聚合状态图标：全部 done=绿勾 / 任一 running=蓝色spinner / 任一 failed=红叉
- 单 tool 默认展开无折叠按钮，多 tool 有 running/failed 时默认展开，全部 done 时默认折叠
- `ToolCallItem` 用 `React.memo` 优化，Props 接口不变

### D. Session 数据稳定回显 + 历史恢复
- `useConversation.loadHistory` 增加 normalizeMessage/normalizeToolCalls 规范化管道
- `chatStore.loadHistory` 增加空 id/重复 id 过滤
- 基于 URL route param `:id` 作为唯一数据源
- 数据流：刷新 → useEffect → loadHistory → API → 规范化 → store → re-render

## 关键取舍与风险

- [Trade-off] Tool 聚合后单个 tool 状态变化触发整个 MessageBubble re-render → 可接受（tool 数量 <10）
- [Risk] history API 返回 toolCalls 可能为 JSON string → 已通过 normalizeToolCalls 防御
- [Risk] SSE flat 格式兼容 → 已通过 `event.payload || event` fallback 防御

## 测试策略

- vitest 单元测试：chatStore.loadHistory 校验逻辑、normalizeToolCalls 边界情况
- 手动集成测试：刷新恢复、IME 输入、Tool 聚合、Session 切换
- 回归测试：运行现有 vitest 测试套件

## Spec Patch

无 — 现有 delta spec 已覆盖所有场景
