---
comet_change: optimize-chat-layout
role: technical-design
canonical_spec: openspec
---

# Chat Layout Optimization Design

## Overview

优化聊天页面布局，参考 ChatGPT 的居中阅读体验。当前消息区域全宽显示，在大屏幕上文本行过长，阅读体验差。

## Architecture

### New Component: ChatContainer

```
frontend/src/features/ai-chat/components/ChatContainer.tsx
```

纯布局组件，无业务逻辑。接受 children，统一约束宽度。

```tsx
interface ChatContainerProps {
  children: React.ReactNode;
}

export function ChatContainer({ children }: ChatContainerProps) {
  return (
    <div className="max-w-[820px] mx-auto w-full px-4 md:px-6 xl:px-8">
      {children}
    </div>
  );
}
```

### Layout Structure After Change

```
ChatInterface.tsx
├── Sidebar (贴左，不变)
└── div.flex-1.flex.flex-col
    ├── Header (全宽，不变)
    ├── main
    │   └── ChatContainer        ← NEW
    │       └── MessageList      ← 去掉自身 px-4
    └── footer
        └── ChatContainer        ← NEW，替换原来的 max-w-4xl div
            └── InputBox
```

### File Changes

| File | Change | LOC |
|------|--------|-----|
| `ChatContainer.tsx` | 新建 | +12 |
| `ChatInterface.tsx` | main 和 footer 各包一层 ChatContainer | ~4 |
| `MessageList.tsx` | 去掉 `px-4` | -1 |
| `MessageBubble.tsx` | `max-w-[80%]` → `max-w-[85%]` | 1 |

### Responsive Breakpoints

| Viewport | Padding | Width |
|----------|---------|-------|
| < 768px | px-4 (16px) | 100% |
| 768-1200px | px-6 (24px) | 100%, up to 820px |
| > 1200px | px-8 (32px) | max-width: 820px, centered |

### Constraints

- No changes to message rendering logic (StreamingRenderer, MarkdownRenderer, ReasoningPanel, ToolCallPanel)
- No changes to SSE event handling (useChatStream, chatApi)
- No changes to store (chatStore)
- No changes to backend
- Sidebar unaffected
- Tailwind config unchanged (using arbitrary value `max-w-[820px]`)

### Testing

- Visual: verify centered layout at 1920px, 1440px, 1024px, 768px, 375px
- Functional: send message, verify streaming, load history, agent selector, logout
- Existing frontend tests pass (vitest)
