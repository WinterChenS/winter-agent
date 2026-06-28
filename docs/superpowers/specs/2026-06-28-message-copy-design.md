---
comet_change: message-copy
role: technical-design
canonical_spec: openspec
---

# Message Copy Feature Design

## Architecture

```
utils/copy.ts          → copyText() tool function
types/message.ts       → Message + rawContent field
components/MessageActions.tsx → Copy button + Copied feedback
components/MessageBubble.tsx  → Integrate MessageActions
hooks/useChatStream.ts → Pass rawContent
store/chatStore.ts     → Support rawContent
```

## Component: MessageActions

Pure presentation component, no business logic.

```tsx
interface MessageActionsProps {
  content: string;       // text to copy (raw markdown or user input)
  label?: string;        // aria-label
}
```

- Default: `opacity-0` (hidden)
- Parent hover → `opacity-100` (visible)
- Click → copy content → show ✓ Copied for 2s → revert
- Mobile: always visible (`sm:opacity-100` or similar)

## Data Flow

**User message:**
1. `useChatStream.send()` creates user message with `rawContent = content.trim()`
2. `MessageActions` copies `msg.rawContent`

**AI message:**
1. SSE deltas accumulate in `content_accumulated` (already happens)
2. On `message.done`, rawContent is set from `content_accumulated`
3. `MessageActions` copies `msg.rawContent`

## Utility: copyText

```typescript
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for older browsers
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand('copy');
      return true;
    } catch {
      return false;
    } finally {
      document.body.removeChild(textarea);
    }
  }
}
```

## Testing

- Unit test: copyText fallback path
- Manual: copy AI message → paste to Typora, verify markdown preserved
- Manual: copy user message → verify plain text
