---
comet_change: ai-chat-layer-rewrite
role: technical-design
canonical_spec: openspec
---

# AI Chat UI Layer Rewrite — Technical Design

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                  FRONTEND (React + Tailwind)                  │
│                                                               │
│  App.tsx                                                      │
│  ├── /chat-v2/:id  →  features/ai-chat/ChatContainer (NEW)   │
│  │   ├── ChatHeader (Agent Selector)                         │
│  │   ├── MessageList (@tanstack/react-virtual)               │
│  │   │   ├── MessageBubble (user/assistant)                  │
│  │   │   │   ├── ReasoningPanel (collapsible)                │
│  │   │   │   ├── ToolCallPanel (collapsible cards)           │
│  │   │   │   └── MarkdownRenderer (react-markdown + Shiki)   │
│  │   │   └── StreamingRenderer (cursor animation)            │
│  │   └── InputBox                                            │
│  ├── /chat/:id     →  ChatInterface (OLD, @deprecated)       │
│  └── /admin/agents →  AdminAgents (Ant Design, unchanged)    │
│                                                               │
│  Store: Zustand chatStore (Map-based, rAF batched)            │
│  Service: chatApi.ts (SSE fetch, new protocol)                │
│  Hooks: useChatStream, useConversation                        │
└──────────────┬───────────────────────────────────────────────┘
               │  POST /api/chat  { message, agentId, conversationId, messageId }
               │  Content-Type: text/event-stream
               ▼
┌──────────────────────────────────────────────────────────────┐
│              SPRING BOOT (WebFlux Gateway)                    │
│                                                               │
│  ChatController:  POST /api/chat → SSE passthrough           │
│  AgentController: GET/POST/PUT/DELETE /api/agents → proxy    │
│  ChatRequest: message + agentId + conversationId + messageId  │
│  WebClient → Python AI Service                                │
└──────────────┬───────────────────────────────────────────────┘
               │  POST /api/v1/generate/stream
               ▼
┌──────────────────────────────────────────────────────────────┐
│            PYTHON AI SERVICE (FastAPI + LangGraph)            │
│                                                               │
│  stream_generate:                                             │
│  1. Load Agent by agentId → inject active_agent              │
│  2. Init graph state with active_agent                        │
│  3. astream_events → map to new SSE protocol                  │
│  4. Async write to PostgreSQL chat_messages on message.done   │
│                                                               │
│  Event Envelope (new):                                        │
│  ├── message.delta      { messageId, agentId, delta }        │
│  ├── message.tool_call  { messageId, agentId, toolCall }     │
│  ├── message.reasoning  { messageId, agentId, delta }        │
│  ├── message.done       { messageId, status, error? }        │
│  └── error              { messageId, error }                  │
└──────────────────────────────────────────────────────────────┘
```

## 2. Data Model

### 2.1 Message (TypeScript / Python / Java aligned)

```typescript
interface Message {
  id: string;                        // UUID v4, frontend-generated
  role: "user" | "assistant" | "system";
  content: string;
  reasoning?: string;                // AI thinking process
  toolCalls?: ToolCall[];            // Tool invocations
  status: "streaming" | "done" | "error";
  agentId?: string;                  // Processing agent
  conversationId?: string;
  createdAt?: number;                // Unix ms
}

interface ToolCall {
  id: string;                        // UUID, Python-generated per invocation
  name: string;
  arguments: Record<string, unknown>;
  status: "pending" | "running" | "done" | "failed";
  result?: unknown;
}
```

### 2.2 Database Schema (PostgreSQL)

```sql
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY,
  conversation_id UUID NOT NULL,
  role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL DEFAULT '',
  reasoning TEXT,
  tool_calls JSONB,
  status VARCHAR(16) DEFAULT 'done' CHECK (status IN ('streaming', 'done', 'error')),
  agent_id VARCHAR(64),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_messages_conv ON chat_messages(conversation_id, created_at);
CREATE INDEX idx_messages_agent ON chat_messages(agent_id, created_at);
```

Python writes to this table asynchronously (via `asyncio.create_task`) after `message.done` is emitted. No blocking of the SSE stream.

## 3. SSE Protocol

### 3.1 Event Types

| Event | Direction | Trigger | Payload |
|-------|-----------|---------|---------|
| `message.delta` | Python → Frontend | LLM generates token | `{ type, messageId, agentId, delta }` |
| `message.tool_call` | Python → Frontend | Tool start / complete | `{ type, messageId, agentId, toolCall: { id, name, arguments, status, result? } }` |
| `message.reasoning` | Python → Frontend | LLM reasoning token | `{ type, messageId, agentId, delta }` |
| `message.done` | Python → Frontend | Stream end | `{ type, messageId, status: "done"\|"error", error? }` |
| `error` | Python → Frontend | Fatal error | `{ type, messageId, error }` |

All events carry `timestamp: number` (Unix ms) in the envelope.

### 3.2 Event Flow (Typical Turn)

```
Frontend                  Python AI Service
   │                            │
   ├─ POST /api/chat ──────────►│ GenerateRequest { messageId, agentId, ... }
   │                            │
   │◄─ message.reasoning ──────┤ (optional, streaming)
   │◄─ message.reasoning ──────┤
   │                            │
   │◄─ message.tool_call ──────┤ { toolCall: { status: "running" } }
   │◄─ message.tool_call ──────┤ { toolCall: { status: "done", result } }
   │                            │
   │◄─ message.delta ──────────┤ (streaming)
   │◄─ message.delta ──────────┤
   │                            │
   │◄─ message.done ───────────┤ { status: "done" }
   │                            │
   │                            ├─ [async] INSERT INTO chat_messages
```

## 4. Frontend Architecture

### 4.1 Zustand Store (chatStore.ts)

```typescript
interface ChatState {
  // State
  messages: Record<string, Message>;
  messageOrder: string[];
  agentId: string | null;
  conversationId: string | null;
  isSending: boolean;

  // Actions
  addMessage: (msg: Message) => void;
  appendDelta: (id: string, delta: string) => void;
  appendReasoning: (id: string, delta: string) => void;
  upsertToolCall: (messageId: string, toolCall: ToolCall) => void;
  completeMessage: (id: string, status: "done" | "error") => void;
  setAgentId: (id: string) => void;
  setConversationId: (id: string) => void;
  setIsSending: (v: boolean) => void;
  loadHistory: (messages: Message[]) => void;
  clearMessages: () => void;
}
```

**Key implementation details:**

```typescript
// rAF batching for appendDelta
let _pendingDeltas = new Map<string, string>();
let _rafId: number | null = null;

appendDelta: (id, delta) => {
  _pendingDeltas.set(id, (_pendingDeltas.get(id) || "") + delta);
  if (_rafId === null) {
    _rafId = requestAnimationFrame(() => {
      set(state => {
        for (const [msgId, text] of _pendingDeltas) {
          if (state.messages[msgId]) {
            state.messages[msgId].content += text;
          }
        }
      });
      _pendingDeltas.clear();
      _rafId = null;
    });
  }
},
```

**Component selector pattern:**

```typescript
// In MessageList.tsx
const orderedMessages = useChatStore(s => 
  s.messageOrder.map(id => s.messages[id])
);
// Only re-renders when messageOrder or the specific message changes
```

### 4.2 Component Tree and Responsibilities

| Component | Responsibility | Props |
|-----------|---------------|-------|
| `ChatContainer` | Layout shell, header, agent selector | — |
| `MessageList` | Virtual scrolling, auto-scroll logic | — |
| `MessageBubble` | Role-based rendering, agent label | `message: Message` |
| `ReasoningPanel` | Collapsible reasoning display | `reasoning: string` |
| `ToolCallPanel` | Tool card with status animation | `toolCall: ToolCall` |
| `MarkdownRenderer` | Markdown + Shiki highlight + LaTeX | `content: string` |
| `StreamingRenderer` | Cursor blink animation | `isStreaming: boolean` |
| `InputBox` | Text input, send, disable while sending | `onSend`, `disabled` |

### 4.3 Shiki Integration

```typescript
// MarkdownRenderer.tsx — lazy load Shiki
const [highlighter, setHighlighter] = useState<Highlighter | null>(null);

useEffect(() => {
  import('shiki').then(async ({ createHighlighter }) => {
    const h = await createHighlighter({
      themes: ['github-dark'],
      langs: ['typescript', 'python', 'java', 'sql', 'json', 'bash', 'markdown'],
    });
    setHighlighter(h);
  });
}, []);

// Use in custom code renderer for react-markdown
```

Languages loaded on-demand; first render uses plain `<pre><code>` fallback.

### 4.4 Virtual Scrolling

```typescript
// MessageList.tsx
import { useVirtualizer } from '@tanstack/react-virtual';

const virtualizer = useVirtualizer({
  count: orderedMessages.length,
  getScrollElement: () => scrollRef.current,
  estimateSize: () => 120, // default estimate; dynamic measurement via measureElement
  overscan: 5,
});
```

Auto-scroll: while `isSending=true` and user is at bottom (within 100px), scroll into view on each new delta. When user scrolls up >100px, show "↓ 回到底部" floating button.

## 5. Backend Changes

### 5.1 Spring Boot

**ChatRequest.java** — add fields:

```java
public record ChatRequest(
    String message,
    @JsonProperty("agentId") String agentId,
    @JsonProperty("conversationId") String conversationId,
    @JsonProperty("messageId") String messageId
) {}
```

**AgentController.java** — new:

```java
@RestController
@RequestMapping("/api/agents")
public class AgentController {
    // GET /api/agents → proxy to Python GET /api/v1/agents/
    // POST /api/agents → proxy to Python POST /api/v1/agents/
    // PUT /api/agents/{id} → proxy to Python PUT /api/v1/agents/{id}
    // DELETE /api/agents/{id} → proxy to Python DELETE /api/v1/agents/{id}
}
```

**AIClient.java** — update `streamGenerate`:

```java
public Flux<String> streamGenerate(String message, String agentId, 
                                    String conversationId, String messageId) {
    GenerateRequest request = new GenerateRequest(message, agentId, conversationId, messageId);
    return webClient.post()
        .uri(aiServiceUrl + "/api/v1/generate/stream")
        .bodyValue(request)
        .retrieve()
        .bodyToFlux(String.class);
}
```

### 5.2 Python AI Service

**schemas.py** — update `GenerateRequest`:

```python
class GenerateRequest(BaseModel):
    message: str
    agent_id: Optional[str] = Field(None, alias="agentId")
    conversation_id: Optional[str] = Field(None, alias="conversationId")
    message_id: Optional[str] = Field(None, alias="messageId")
```

**event_envelope.py** — new functions:

```python
def envelope_message_delta(trace_ctx, message_id: str, delta: str) -> dict:
    """message.delta — token-level text increment."""

def envelope_message_tool_call(trace_ctx, message_id: str, 
                               tool_call: dict) -> dict:
    """message.tool_call — tool invocation status."""

def envelope_message_reasoning(trace_ctx, message_id: str, delta: str) -> dict:
    """message.reasoning — thinking process increment."""

def envelope_message_done(trace_ctx, message_id: str, 
                          status: str = "done", error: str = None) -> dict:
    """message.done — stream completion."""
```

**chat.py** — key changes in `stream_generate`:

```python
# 1. Load agent by agentId
agent_id = request.agent_id
if agent_id:
    agent_def = await agent_repo.get(agent_id)
    if not agent_def:
        yield to_sse_data(envelope_message_done(trace_ctx, request.message_id, 
                                                 status="error", error=f"Agent not found: {agent_id}"))
        return
    active_agent = agent_id

# 2. Inject into graph state
inputs["active_agent"] = active_agent or "default"

# 3. Stream with new event types
async for event in graph.astream_events(inputs, config=config, version="v2"):
    mapped = map_langgraph_event_to_new_protocol(event, event_ctx, message_id, agent_id)
    for envelope in mapped:
        yield to_sse_data(envelope)

# 4. Emit message.done
yield to_sse_data(envelope_message_done(trace_ctx, message_id, status="done"))

# 5. Async persist
asyncio.create_task(save_message_to_db(message_id, ...))
```

## 6. Migration Strategy

**Phase: `/chat-v2` parallel validation → route switch**

```
Step 1: Build new ChatContainer under /chat-v2/:id
        Old /chat/:id remains active, users unaffected

Step 2: Internal validation on /chat-v2
        - Streaming, reasoning, tool calls, agent switch
        - Long conversation (1000+ messages)
        - Error states

Step 3: Route switch in App.tsx:
        /chat/:id → ChatContainer (new)
        /chat-legacy/:id → ChatInterface (old, for rollback)

Step 4: Deprecate old files with comments:
        // @deprecated since v2.0, replaced by features/ai-chat/
        // Remove after v2.0 stabilization period
```

## 7. Testing

| Layer | Tool | Scope |
|-------|------|-------|
| Python unit | pytest | `event_envelope.py` output format for each new event type |
| Python integration | pytest + httpx | `stream_generate` SSE event sequence; agentId routing; invalid agentId error |
| Spring Boot | WebTestClient | Agent CRUD proxy forwarding; Chat SSE passthrough; agentId in request |
| Frontend unit | vitest | chatStore actions: addMessage, appendDelta, appendReasoning, upsertToolCall, rAF batching |
| Frontend component | vitest + testing-library | MessageBubble role rendering; ReasoningPanel expand/collapse; ToolCallPanel status display |
| E2E | Playwright | Full flow: Agent select → send message → stream receive → reasoning expand → tool_call display → message.done → history reload |
| Protocol | `scripts/test_chat_scenarios.py` (updated) | SSE event format validation against spec |
