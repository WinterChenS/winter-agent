---
comet_change: optimize-chat-ui-rendering
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-27-optimize-chat-ui-rendering
status: final
---

# Optimize Chat UI Rendering — Technical Design

## 1. SSE EventEnvelope Parsing Fix

### Context

Backend `EventEnvelope` wraps business fields in a `payload` object:

```json
{
  "type": "message.delta",
  "schemaVersion": "1.0",
  "conversationId": "uuid",
  "agentId": "agent-001",
  "timestamp": 1234567890000,
  "payload": {
    "messageId": "uuid",
    "delta": "hello"
  }
}
```

Frontend `chatApi.ts` currently reads `event.messageId`, `event.delta`, `event.toolCall` directly from the top level, missing all business data.

### Implementation

**File**: `frontend/src/features/ai-chat/services/chatApi.ts`

Add payload unwrap at the top of `handleEvent`:

```typescript
function handleEvent(event: SseEvent): void {
  const p = (event.payload || event) as Record<string, unknown>;
  const { type } = event;
  const messageId = p.messageId as string;
  const delta = p.delta as string;
  const toolCall = p.toolCall as ToolCall | undefined;
  const status = p.status as string | undefined;
  // ... switch cases use p.* for business fields
}
```

Update `SseEvent` interface to reflect the actual EventEnvelope structure with both `payload` fields and flat fallback fields.

**Event type mapping** (payload field → handler usage):

| Event Type | Payload Fields Used |
|---|---|
| `agent.started` | `payload.agent`, `payload.display` |
| `tool.started` | `payload.tool_call_id`, `payload.tool`, `payload.arguments` |
| `tool.finished` | `payload.tool_call_id`, `payload.tool`, `payload.result` |
| `tool.failed` | `payload.tool_call_id`, `payload.tool`, `payload.error` |
| `image.uploaded` | `payload.url`, `payload.filename` |
| `message.tool_call` | `payload.toolCall` |
| `message.delta` | `payload.messageId`, `payload.delta` |
| `message.reasoning` | `payload.messageId`, `payload.delta` |
| `message.done` / `conversation.finished` | `payload.messageId`, `payload.status` |
| `error` | `payload.messageId` |
| `conversation.started` | (no business fields needed) |

## 2. IME Input Guard

### Context

`InputBox.tsx` `handleKeyDown` directly sends on Enter without checking IME composition state. CJK IME users pressing Enter to confirm candidate characters will incorrectly trigger message submission.

### Implementation

**File**: `frontend/src/features/ai-chat/components/InputBox.tsx`

```typescript
const isComposing = useRef(false);

const handleCompositionStart = useCallback(() => {
  isComposing.current = true;
}, []);

const handleCompositionEnd = useCallback(() => {
  isComposing.current = false;
}, []);

const handleKeyDown = useCallback(
  (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (isComposing.current) return; // IME guard
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  },
  [handleSend]
);
```

Textarea gets `onCompositionStart={handleCompositionStart}` and `onCompositionEnd={handleCompositionEnd}`.

**Design rationale**: `useRef` over `useState` — composition state changes must not trigger re-renders, which would reset IME candidate window position. Safari compatibility is handled by the ref guard at the top of `handleKeyDown`, no need to check `keyCode === 229` separately.

## 3. Tool Execution Panel (Aggregated Display)

### Context

Current `ToolCallPanel.tsx` renders each tool call as a separate card. For multi-tool scenarios (search + browser + sandbox), this produces excessive vertical space and no unified execution status overview.

### Implementation

**File**: `frontend/src/features/ai-chat/components/ToolCallPanel.tsx` (rewrite)

Component tree:

```
ToolCallPanel ({ toolCalls: ToolCall[] })
├── Header (always visible)
│   ├── Aggregate status icon (green ✓ / blue spinner / red ✗)
│   ├── Tool count badge ("3 tools")
│   └── Collapse toggle (only when toolCalls.length > 1)
└── Body (visible when expanded)
    └── ToolCallItem[] (memo'd per tool)
        ├── Status icon
        ├── Tool name (monospace)
        ├── Status text (executing.../completed/failed)
        └── Result expander (when done/failed)
```

**Collapse behavior**:

| Condition | Default State |
|---|---|
| 1 tool call | Expanded, no collapse button |
| 2+ tool calls, all done | Collapsed |
| 2+ tool calls, any running | Expanded |
| 2+ tool calls, any failed | Expanded |

**Aggregate status icon**:
- All done → green checkmark
- Any running/pending → blue animated spinner
- Any failed (and no running) → red X

**Performance**: `ToolCallItem` wrapped in `React.memo`. Each item only re-renders when its own `ToolCall` object reference changes (Zustand creates new references on `upsertToolCall`).

**Props interface unchanged**: `toolCalls: ToolCall[]` — `MessageBubble` requires zero changes.

## 4. Session Data Stable Rendering & History Restore

### Context

Session list is stored in `localStorage`. On refresh/navigation, messages must be re-fetched from the history API. The history API response may have `toolCalls` as JSON strings and missing optional fields.

### Implementation

**File**: `frontend/src/features/ai-chat/hooks/useConversation.ts`

Add normalization pipeline before store insertion:

```typescript
function normalizeMessage(msg: Record<string, unknown>): Message {
  return {
    id: msg.id as string,
    role: msg.role as Message['role'],
    content: (msg.content as string) || '',
    reasoning: (msg.reasoning as string) || undefined,
    status: (msg.status as Message['status']) || 'done',
    toolCalls: normalizeToolCalls(msg.toolCalls),
    agentId: (msg.agentId as string) || undefined,
    conversationId: (msg.conversationId as string) || undefined,
    createdAt: typeof msg.createdAt === 'number' ? msg.createdAt : undefined,
    images: (msg.images as Message['images']) || {},
  };
}

function normalizeToolCalls(toolCalls: unknown): ToolCall[] {
  if (!toolCalls) return [];
  if (typeof toolCalls === 'string') {
    try { return JSON.parse(toolCalls); }
    catch { return []; }
  }
  return Array.isArray(toolCalls) ? toolCalls as ToolCall[] : [];
}
```

**File**: `frontend/src/features/ai-chat/store/chatStore.ts`

Add validation to `loadHistory`: skip messages with empty/null `id`, deduplicate by `id`.

**File**: `frontend/src/pages/ChatInterface.tsx`

Existing logic already uses `routeSessionId` as single source of truth. No structural changes needed — verify that session switch path (clearMessages → loadHistory → navigate) is race-condition free.

### Data Flow (Refresh Restore)

```
Browser refresh at /chat/:id
  → ChatInterface mount
  → useEffect(routeSessionId)
  → loadHistory(routeSessionId)
  → GET /api/chat/history/:id
  → normalizeMessage for each message
  → store.loadHistory(normalizedMessages)
  → MessageList reads store.messageOrder + store.messages
  → ToolCallPanel renders aggregated tool calls per message
```

### Data Flow (Live Streaming)

```
User sends message
  → useChatStream.send(content)
  → addMessage(user, status: "done")
  → addMessage(assistant, status: "streaming")
  → sendChatMessage({ message, agentId, conversationId, messageId })
  → SSE events arrive
  → handleEvent unwraps payload
  → store updates (appendDelta, upsertToolCall, completeMessage)
  → React re-renders affected components
```

## 5. Error Handling

- **SSE parse failure**: `try/catch` around `JSON.parse(data)` with `console.warn`, skip malformed events
- **History API failure**: throw error, let `ChatInterface` error boundary or inline error state handle it
- **Malformed toolCalls**: `normalizeToolCalls` returns `[]` on any parse failure
- **Empty/null message id**: `loadHistory` skips invalid entries
- **Network interruption during streaming**: `fetch` rejection caught in `useChatStream.send`, sets message status to `error`

## 6. Testing Strategy

### Unit Tests (vitest)
- `chatStore.loadHistory`: empty array, duplicate ids, missing status, null id
- `normalizeToolCalls`: JSON string, already-parsed array, null, empty string, malformed JSON
- `handleEvent`: payload-wrapped event, flat event, missing payload fields

### Manual Integration Tests
1. Send message → wait for tool execution → refresh page → verify all messages/tools/order match
2. Chinese IME: type pinyin, press Enter to select candidate → verify no send
3. English: type text, press Enter → verify send
4. Multi-tool scenario: verify panel collapse/expand, status icon transitions
5. Session switch: Session A → Session B → Session A → verify correct data each time
6. Empty session: navigate to new chat → verify empty state message
