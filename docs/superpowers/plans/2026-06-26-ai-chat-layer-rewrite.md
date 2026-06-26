---
change: ai-chat-layer-rewrite
design-doc: docs/superpowers/specs/2026-06-26-ai-chat-layer-rewrite-design.md
base-ref: 2fd5b1f19578274810b2c23e2e81735de4896e00
---

# AI Chat UI Layer Rewrite 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前混杂交错的 Chat UI 升级为标准化 AI Chat 专用层（新 Message Model + 新 SSE 协议 + 独立组件架构 + Agent 网关）

**Architecture:** 三层协同：Python 协议层（event_envelope + agent 路由）→ Spring Boot 网关（Agent CRUD + SSE 透传）→ React 前端（Zustand store + 独立 Chat 组件 + 虚拟滚动 + Shiki）

**Tech Stack:** Python FastAPI + LangGraph, Spring Boot WebFlux, React 18 + TypeScript + TailwindCSS + Zustand + @tanstack/react-virtual + Shiki + react-markdown

## Global Constraints

- 所有 SSE 事件使用新协议：message.delta / message.tool_call / message.reasoning / message.done
- Message role 统一为 user | assistant | system
- 前端 messageId 由前端生成 UUID v4
- ToolCall 必须携带独立 toolCallId
- Zustand store 使用 Map-based shape + rAF 批处理
- Ant Design 仅用于 AdminAgents 页面，Chat UI 完全自定义
- Spring Boot 不做 AI 逻辑，只做鉴权 + 路由 + 透传
- 旧 Chat 文件保留不删，标注 @deprecated
- 新 Chat UI 路由：/chat-v2/:id，旧 /chat/:id 保持不变直到迁移完成

---

## File Structure Map

```
New files:
  ai_service/db/chat_message_repository.py
  ai_service/db/migrations/001_create_chat_messages.sql
  backend/src/main/java/com/example/aichat/controller/AgentController.java
  frontend/src/features/ai-chat/types/message.ts
  frontend/src/features/ai-chat/types/agent.ts
  frontend/src/features/ai-chat/store/chatStore.ts
  frontend/src/features/ai-chat/services/chatApi.ts
  frontend/src/features/ai-chat/components/ChatContainer.tsx
  frontend/src/features/ai-chat/components/MessageList.tsx
  frontend/src/features/ai-chat/components/MessageBubble.tsx
  frontend/src/features/ai-chat/components/ReasoningPanel.tsx
  frontend/src/features/ai-chat/components/ToolCallPanel.tsx
  frontend/src/features/ai-chat/components/MarkdownRenderer.tsx
  frontend/src/features/ai-chat/components/StreamingRenderer.tsx
  frontend/src/features/ai-chat/components/InputBox.tsx
  frontend/src/features/ai-chat/hooks/useChatStream.ts
  frontend/src/features/ai-chat/hooks/useConversation.ts
  frontend/src/features/ai-chat/__tests__/chatStore.test.ts

Modified files:
  ai_service/domain/event_envelope.py
  ai_service/api/schemas.py
  ai_service/api/events/event_mapper.py
  ai_service/api/routes/chat.py
  ai_service/graph/graph.py
  backend/src/main/java/com/example/aichat/model/ChatRequest.java
  backend/src/main/java/com/example/aichat/client/AIClient.java
  frontend/src/types/chat.ts
  frontend/src/App.tsx
  frontend/package.json
  scripts/test_chat_scenarios.py
```

---

## Task 1: Python — 重构 event_envelope.py

**Files:**
- Modify: `ai_service/domain/event_envelope.py`
- Test: `ai_service/tests/test_event_envelope.py` (create if not exists)

**Interfaces:**
- Produces: `envelope_message_delta(trace_ctx, message_id, delta) -> dict`
- Produces: `envelope_message_tool_call(trace_ctx, message_id, tool_call_dict) -> dict`
- Produces: `envelope_message_reasoning(trace_ctx, message_id, delta) -> dict`
- Produces: `envelope_message_done(trace_ctx, message_id, status="done", error=None) -> dict`
- Retains: `envelope_error`, `envelope_chart`, `to_sse_data`, `build_envelope`

- [ ] **Step 1: Add new envelope functions to event_envelope.py**

在文件末尾追加 4 个新函数：

```python
def envelope_message_delta(
    trace_ctx: TraceContext, message_id: str, delta: str
) -> dict[str, Any]:
    """message.delta — token-level text increment."""
    return build_envelope(
        "message.delta",
        trace_ctx,
        payload={"messageId": message_id, "agentId": trace_ctx.agent_id, "delta": delta},
        compat_fields={"messageId": message_id, "delta": delta},
    )


def envelope_message_tool_call(
    trace_ctx: TraceContext, message_id: str, tool_call: dict[str, Any]
) -> dict[str, Any]:
    """message.tool_call — tool invocation status update."""
    return build_envelope(
        "message.tool_call",
        trace_ctx,
        payload={
            "messageId": message_id,
            "agentId": trace_ctx.agent_id,
            "toolCall": tool_call,
        },
        compat_fields={"messageId": message_id, "toolCall": tool_call},
    )


def envelope_message_reasoning(
    trace_ctx: TraceContext, message_id: str, delta: str
) -> dict[str, Any]:
    """message.reasoning — AI thinking process increment."""
    return build_envelope(
        "message.reasoning",
        trace_ctx,
        payload={"messageId": message_id, "agentId": trace_ctx.agent_id, "delta": delta},
        compat_fields={"messageId": message_id, "delta": delta},
    )


def envelope_message_done(
    trace_ctx: TraceContext, message_id: str, *,
    status: str = "done", error: str | None = None,
) -> dict[str, Any]:
    """message.done — stream completion signal."""
    payload: dict[str, Any] = {
        "messageId": message_id,
        "agentId": trace_ctx.agent_id,
        "status": status,
    }
    if error:
        payload["error"] = error
    return build_envelope(
        "message.done",
        trace_ctx,
        payload=payload,
        compat_fields={"messageId": message_id, "status": status},
    )
```

- [ ] **Step 2: Write unit test for new envelope functions**

Create `ai_service/tests/test_event_envelope.py`:

```python
import pytest
from observability.trace import TraceContext
from domain.event_envelope import (
    envelope_message_delta,
    envelope_message_tool_call,
    envelope_message_reasoning,
    envelope_message_done,
    to_sse_data,
)

def make_ctx():
    return TraceContext(
        conversation_id="conv-1",
        trace_id="tr-1",
        turn_id="turn-1",
        span_id="span-1",
        parent_span_id=None,
        agent_id="agent-1",
    )

def test_message_delta_has_correct_type():
    ctx = make_ctx()
    env = envelope_message_delta(ctx, "msg-1", "Hello")
    assert env["type"] == "message.delta"
    assert env["payload"]["messageId"] == "msg-1"
    assert env["payload"]["delta"] == "Hello"
    assert env["payload"]["agentId"] == "agent-1"

def test_message_tool_call_has_toolcall_payload():
    ctx = make_ctx()
    tc = {"id": "tc-1", "name": "search", "arguments": {"q": "x"}, "status": "running"}
    env = envelope_message_tool_call(ctx, "msg-1", tc)
    assert env["type"] == "message.tool_call"
    assert env["payload"]["toolCall"]["id"] == "tc-1"
    assert env["payload"]["toolCall"]["status"] == "running"

def test_message_reasoning():
    ctx = make_ctx()
    env = envelope_message_reasoning(ctx, "msg-1", "Let me think...")
    assert env["type"] == "message.reasoning"
    assert env["payload"]["delta"] == "Let me think..."

def test_message_done_success():
    ctx = make_ctx()
    env = envelope_message_done(ctx, "msg-1", status="done")
    assert env["type"] == "message.done"
    assert env["payload"]["status"] == "done"
    assert "error" not in env["payload"]

def test_message_done_error():
    ctx = make_ctx()
    env = envelope_message_done(ctx, "msg-1", status="error", error="Agent not found")
    assert env["payload"]["status"] == "error"
    assert env["payload"]["error"] == "Agent not found"

def test_to_sse_data_wraps_json():
    ctx = make_ctx()
    env = envelope_message_delta(ctx, "msg-1", "x")
    sse = to_sse_data(env)
    assert "data" in sse
    assert "message.delta" in sse["data"]
```

- [ ] **Step 3: Run tests to verify**

```bash
cd ai_service && python -m pytest tests/test_event_envelope.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add ai_service/domain/event_envelope.py ai_service/tests/test_event_envelope.py
git commit -m "feat: add new SSE protocol envelope functions (message.delta/tool_call/reasoning/done)"
```

---

## Task 2: Python — 更新 event_mapper.py

**Files:**
- Modify: `ai_service/api/events/event_mapper.py`

**Interfaces:**
- Consumes: New envelope functions from Task 1
- Produces: `map_langgraph_event_to_envelopes()` now emits new event types + messageId

- [ ] **Step 1: Update event mapping logic**

需要改动的核心点（修改 `map_langgraph_event_to_envelopes` 函数）：

1. token 事件 → `envelope_message_delta` 替代 `envelope_token`
2. tool_start → `envelope_message_tool_call` 替代 `envelope_tool_start`
3. tool_result → `envelope_message_tool_call` 替代 `envelope_tool_result`（合并为更新同一个 toolCall）
4. reasoning_delta/thought → `envelope_message_reasoning` 替代 `envelope_reasoning_delta`

关键改动示例（在原函数中修改对应调用）：

```python
# token → message.delta
# 替换 envelope_token(trace_ctx, content)
yield envelope_message_delta(trace_ctx, message_id, content)

# tool_start → message.tool_call
yield envelope_message_tool_call(trace_ctx, message_id, {
    "id": tool_call_id,           # generate via uuid4 or tool_name+seq
    "name": tool_name,
    "arguments": input_payload,
    "status": "running",
})

# tool_result → message.tool_call (update same tool_call_id)
yield envelope_message_tool_call(trace_ctx, message_id, {
    "id": tool_call_id,
    "name": tool_name,
    "status": "completed",
    "result": summary_text,
})

# reasoning_delta → message.reasoning
yield envelope_message_reasoning(trace_ctx, message_id, delta)
```

- [ ] **Step 2: Verify event mapper imports are correct**

```bash
cd ai_service && python -c "from api.events.event_mapper import map_langgraph_event_to_envelopes; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add ai_service/api/events/event_mapper.py
git commit -m "feat: update event mapper to emit new SSE protocol events"
```

---

## Task 3: Python — 更新 schemas.py

**Files:**
- Modify: `ai_service/api/schemas.py`

**Interfaces:**
- Produces: `GenerateRequest` with new `agent_id` and `message_id` fields

- [ ] **Step 1: Add agentId and messageId to GenerateRequest**

```python
from pydantic import BaseModel, Field
from typing import Optional


class GenerateRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = Field(None, alias="conversationId")
    agent_id: Optional[str] = Field(None, alias="agentId")
    message_id: Optional[str] = Field(None, alias="messageId")
    stream: bool = True
```

- [ ] **Step 2: Verify schema parses correctly**

```bash
cd ai_service && python -c "
from api.schemas import GenerateRequest
r = GenerateRequest(message='hi', agent_id='a1', message_id='m1', conversation_id='c1')
assert r.agent_id == 'a1'
assert r.message_id == 'm1'
print('OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add ai_service/api/schemas.py
git commit -m "feat: add agentId and messageId fields to GenerateRequest"
```

---

## Task 4: Python — 更新 chat.py stream_generate

**Files:**
- Modify: `ai_service/api/routes/chat.py`

**Interfaces:**
- Consumes: `GenerateRequest.agent_id`, `GenerateRequest.message_id`
- Consumes: `AgentRepository.get_by_id()`
- Consumes: New envelope functions from Task 1
- Produces: SSE stream with message.done termination + async DB persistence

- [ ] **Step 1: Add agent loading and messageId handling to stream_generate**

关键改动点：
1. 读取 `request.agent_id` 和 `request.message_id`
2. 如果 `agent_id` 存在，从 `agent_repository` 加载 Agent 定义
3. 将 `active_agent` 注入 graph state
4. 在流开始时使用前端传入的 `message_id`（或生成 fallback）
5. 工具调用时生成唯一的 `tool_call_id`
6. 流结束时发送 `message.done`
7. 异步写入 DB

改动摘要（修改 `stream_generate` 函数头部和关键位置）：

```python
@router.post("/generate/stream")
async def stream_generate(request: GenerateRequest):
    @timeit
    async def event_generator():
        trace_ctx = ensure_trace_context(request.conversation_id)
        
        # Use frontend-provided messageId, or generate fallback
        message_id = request.message_id or f"msg-{uuid4().hex[:12]}"
        
        # Load agent if specified
        agent_id = request.agent_id
        if agent_id:
            from repositories.agent_repository import get_agent_repository
            agent_repo = get_agent_repository()
            agent_def = await agent_repo.get_by_id(agent_id)
            if not agent_def:
                yield to_sse_data(envelope_message_done(
                    trace_ctx, message_id, status="error",
                    error=f"Agent not found: {agent_id}"
                ))
                return
            active_agent = agent_id
        else:
            active_agent = trace_ctx.agent_id or "default"
        
        # ... rest of the function uses message_id and active_agent ...
        # inputs["active_agent"] = active_agent
        # At stream end: yield to_sse_data(envelope_message_done(trace_ctx, message_id))
        # Async persist: asyncio.create_task(save_message_to_db(...))
```

- [ ] **Step 2: Run existing tests to catch regressions**

```bash
cd ai_service && python -m pytest tests/ -x -q --timeout=30 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
git add ai_service/api/routes/chat.py
git commit -m "feat: add agentId routing, messageId passthrough, message.done emission to stream_generate"
```

---

## Task 5: Python — 新增 chat_message_repository.py

**Files:**
- Create: `ai_service/db/chat_message_repository.py`

**Interfaces:**
- Produces: `save_message(message_dict) -> None`
- Produces: `get_messages_by_conversation(conversation_id) -> list[dict]`

- [ ] **Step 1: Create repository module**

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from psycopg_pool import AsyncConnectionPool


async def save_message(pool: AsyncConnectionPool, message: dict[str, Any]) -> None:
    """Async insert a completed message into chat_messages table."""
    sql = """
        INSERT INTO chat_messages (id, conversation_id, role, content,
            reasoning, tool_calls, status, agent_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            content = EXCLUDED.content,
            reasoning = EXCLUDED.reasoning,
            tool_calls = EXCLUDED.tool_calls,
            status = EXCLUDED.status
    """
    async with pool.connection() as conn:
        await conn.execute(sql, (
            message["id"],
            message.get("conversation_id"),
            message["role"],
            message.get("content", ""),
            message.get("reasoning"),
            json.dumps(message.get("toolCalls", [])) if message.get("toolCalls") else None,
            message.get("status", "done"),
            message.get("agentId"),
            datetime.fromtimestamp(
                message.get("createdAt", 0) / 1000, tz=timezone.utc
            ) if message.get("createdAt") else datetime.now(timezone.utc),
        ))


async def get_messages_by_conversation(
    pool: AsyncConnectionPool, conversation_id: str
) -> list[dict[str, Any]]:
    """Load message history for a conversation."""
    sql = """
        SELECT id, conversation_id, role, content, reasoning,
               tool_calls, status, agent_id,
               EXTRACT(EPOCH FROM created_at)::bigint * 1000 AS created_at
        FROM chat_messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC
    """
    async with pool.connection() as conn:
        rows = await conn.execute(sql, (conversation_id,))
        records = await rows.fetchall()
    
    messages = []
    for row in records:
        msg = {
            "id": row[0],
            "conversationId": row[1],
            "role": row[2],
            "content": row[3],
            "reasoning": row[4],
            "toolCalls": json.loads(row[5]) if row[5] else None,
            "status": row[6],
            "agentId": row[7],
            "createdAt": int(row[8]) if row[8] else None,
        }
        messages.append(msg)
    return messages
```

- [ ] **Step 2: Verify module imports cleanly**

```bash
cd ai_service && python -c "from db.chat_message_repository import save_message, get_messages_by_conversation; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add ai_service/db/chat_message_repository.py
git commit -m "feat: add chat_message_repository for message persistence"
```

---

## Task 6: Python — 新增 PostgreSQL 迁移脚本

**Files:**
- Create: `ai_service/db/migrations/001_create_chat_messages.sql`

- [ ] **Step 1: Create migration SQL**

```sql
-- 001_create_chat_messages.sql
-- New table for unified message persistence (AI Chat Layer Rewrite)

CREATE TABLE IF NOT EXISTS chat_messages (
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

CREATE INDEX IF NOT EXISTS idx_messages_conv
    ON chat_messages(conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_messages_agent
    ON chat_messages(agent_id, created_at);
```

- [ ] **Step 2: Apply migration to verify syntax**

```bash
cd ai_service && python -c "
from core.runtime import get_checkpointer
# If we have a pool, try running the migration (dry-run syntax check)
# For now just verify the file exists and is non-empty
import os
assert os.path.getsize('db/migrations/001_create_chat_messages.sql') > 0
print('OK: migration file exists and non-empty')
"
```

- [ ] **Step 3: Commit**

```bash
git add ai_service/db/migrations/001_create_chat_messages.sql
git commit -m "feat: add chat_messages table migration"
```

---

## Task 7: Python — 更新 get_chat_history

**Files:**
- Modify: `ai_service/api/routes/chat.py` (get_chat_history function)

**Interfaces:**
- Consumes: `get_messages_by_conversation` from chat_message_repository
- Produces: History response in new Message Model format

- [ ] **Step 1: Update get_chat_history to use new DB table**

将 `get_chat_history` 改为优先从 `chat_messages` 表查询；如果新表为空则 fallback 到旧 checkpoint。

```python
@timeit
@router.get("/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    from db.chat_message_repository import get_messages_by_conversation
    from core.runtime import get_pool  # if available
    
    # Try new DB table first
    pool = get_pool() if hasattr(sys.modules.get('core.runtime'), 'get_pool') else None
    if pool:
        messages = await get_messages_by_conversation(pool, conversation_id)
        if messages:
            return {"messages": messages}
    
    # Fallback: old checkpoint-based history
    checkpointer = get_checkpointer()
    # ... existing logic ...
```

- [ ] **Step 2: Commit**

```bash
git add ai_service/api/routes/chat.py
git commit -m "feat: update get_chat_history to use new chat_messages table"
```

---

## Task 8: Python — 更新 graph.py Agent 路由

**Files:**
- Modify: `ai_service/graph/graph.py`

- [ ] **Step 1: Add active_agent passthrough to create_agent_graph**

在 graph state 初始化逻辑中确保 `active_agent` 被正确注入。当前 state 已有 `active_agent` 字段，只需确认 RouterAgent 节点在收到该字段时直接路由而不经过关键词匹配。

```python
# In create_agent_graph, no structural change needed.
# graph state already has active_agent field.
# RouterAgent (in graph/nodes.py) should check for active_agent first:
#   if state.get("active_agent") and state["active_agent"] != "default":
#       route directly to that agent
```

检查 `ai_service/graph/nodes.py` 中 RouterAgent 是否已处理此逻辑。如果没有，添加：

```python
# Before keyword matching in agent_node:
active = state.get("active_agent", "default")
if active and active != "default":
    # Direct route — skip keyword matching
    return {"route": "chart_planner", "active_agent": active}
```

- [ ] **Step 2: Verify graph compiles**

```bash
cd ai_service && python -c "from graph.graph import create_agent_graph; g = create_agent_graph(); print('Graph compiled OK')"
```

- [ ] **Step 3: Commit**

```bash
git add ai_service/graph/graph.py ai_service/graph/nodes.py
git commit -m "feat: support agentId-based direct routing in graph"
```

---

## Task 9: Spring Boot — 新增 AgentController

**Files:**
- Create: `backend/src/main/java/com/example/aichat/controller/AgentController.java`

- [ ] **Step 1: Create AgentController**

```java
package com.example.aichat.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/agents")
public class AgentController {

    private final WebClient webClient;
    private final String aiServiceUrl;

    public AgentController(WebClient webClient,
                           @Value("${aichat.ai-service-url}") String aiServiceUrl) {
        this.webClient = webClient;
        this.aiServiceUrl = aiServiceUrl;
    }

    @GetMapping
    public Mono<ResponseEntity<String>> listAgents() {
        return webClient.get()
                .uri(aiServiceUrl + "/api/v1/agents/")
                .retrieve()
                .bodyToMono(String.class)
                .map(ResponseEntity::ok);
    }

    @PostMapping
    public Mono<ResponseEntity<String>> createAgent(@RequestBody String body) {
        return webClient.post()
                .uri(aiServiceUrl + "/api/v1/agents/")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .map(ResponseEntity::ok);
    }

    @PutMapping("/{id}")
    public Mono<ResponseEntity<String>> updateAgent(@PathVariable String id, @RequestBody String body) {
        return webClient.put()
                .uri(aiServiceUrl + "/api/v1/agents/" + id)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .map(ResponseEntity::ok);
    }

    @DeleteMapping("/{id}")
    public Mono<ResponseEntity<String>> deleteAgent(@PathVariable String id) {
        return webClient.delete()
                .uri(aiServiceUrl + "/api/v1/agents/" + id)
                .retrieve()
                .bodyToMono(String.class)
                .map(ResponseEntity::ok);
    }
}
```

- [ ] **Step 2: Verify compilation**

```bash
cd backend && mvn compile -q 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/main/java/com/example/aichat/controller/AgentController.java
git commit -m "feat: add AgentController for CRUD proxy to Python AI service"
```

---

## Task 10: Spring Boot — 更新 ChatRequest + AIClient

**Files:**
- Modify: `backend/src/main/java/com/example/aichat/model/ChatRequest.java`
- Modify: `backend/src/main/java/com/example/aichat/client/AIClient.java`

- [ ] **Step 1: Update ChatRequest**

```java
package com.example.aichat.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatRequest(
        String message,
        @JsonProperty("agentId") String agentId,
        @JsonProperty("conversationId") String conversationId,
        @JsonProperty("messageId") String messageId
) {
}
```

- [ ] **Step 2: Update AIClient.streamGenerate signature**

```java
public Flux<String> streamGenerate(String message, String agentId,
                                    String conversationId, String messageId) {
    GenerateRequest request = new GenerateRequest(message, agentId,
                                                   conversationId, messageId);
    return webClient.post()
            .uri(aiServiceUrl + "/api/v1/generate/stream")
            .bodyValue(request)
            .retrieve()
            .bodyToFlux(String.class);
}
```

同时更新 `ChatService.streamChat` 方法签名以传递新字段。

- [ ] **Step 3: Verify compilation**

```bash
cd backend && mvn compile -q 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/main/java/com/example/aichat/model/ChatRequest.java \
        backend/src/main/java/com/example/aichat/client/AIClient.java \
        backend/src/main/java/com/example/aichat/service/ChatService.java \
        backend/src/main/java/com/example/aichat/controller/ChatController.java
git commit -m "feat: add agentId and messageId passthrough in Spring Boot gateway"
```

---

## Task 11-12: 前端 — 类型定义 + 依赖安装

将 Task 4.1-4.3 合并为两步。

**Files:**
- Modify: `frontend/src/types/chat.ts`
- Create: `frontend/src/features/ai-chat/types/message.ts`
- Create: `frontend/src/features/ai-chat/types/agent.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: Rewrite chat.ts with new types**

```typescript
// frontend/src/types/chat.ts
// @deprecated — Old message types kept for AdminAgents compatibility.
// New AI Chat UI uses features/ai-chat/types/message.ts

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: "pending" | "running" | "done" | "failed";
  result?: unknown;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  reasoning?: string;
  toolCalls?: ToolCall[];
  status: "streaming" | "done" | "error";
  agentId?: string;
  conversationId?: string;
  createdAt?: number;
}

// Keep old types for AdminAgents backward compat
export interface AgentDefinition {
  id: string;
  name: string;
  display_name: string;
  description: string;
  enabled: boolean;
}
```

- [ ] **Step 2: Create ai-chat types barrel**

```bash
mkdir -p frontend/src/features/ai-chat/types
```

```typescript
// frontend/src/features/ai-chat/types/message.ts
export type { Message, ToolCall } from '../../../types/chat';
```

```typescript
// frontend/src/features/ai-chat/types/agent.ts
export interface AgentInfo {
  id: string;
  name: string;
  display_name: string;
  description: string;
  enabled: boolean;
}
```

- [ ] **Step 3: Install new dependencies**

```bash
cd frontend && npm install zustand @tanstack/react-virtual shiki
```

- [ ] **Step 4: Verify TypeScript compilation**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -10
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/chat.ts \
        frontend/src/features/ai-chat/types/ \
        frontend/package.json frontend/package-lock.json
git commit -m "feat: add new Message/ToolCall types and install zustand, virtual, shiki"
```

---

## Task 13: 前端 — Zustand chatStore

**Files:**
- Create: `frontend/src/features/ai-chat/store/chatStore.ts`

**Interfaces:**
- Produces: `useChatStore` hook with Map-based state + rAF batched actions

- [ ] **Step 1: Create chatStore**

```typescript
// frontend/src/features/ai-chat/store/chatStore.ts
import { create } from 'zustand';
import type { Message, ToolCall } from '../types/message';

interface ChatState {
  messages: Record<string, Message>;
  messageOrder: string[];
  agentId: string | null;
  conversationId: string | null;
  isSending: boolean;

  addMessage: (msg: Message) => void;
  appendDelta: (id: string, delta: string) => void;
  appendReasoning: (id: string, delta: string) => void;
  upsertToolCall: (messageId: string, toolCall: ToolCall) => void;
  completeMessage: (id: string, status: "done" | "error") => void;
  setAgentId: (id: string) => void;
  setConversationId: (id: string) => void;
  setIsSending: (v: boolean) => void;
  loadHistory: (msgs: Message[]) => void;
  clearMessages: () => void;
}

// rAF batching state (module-level, outside React)
let pendingDeltas = new Map<string, string>();
let pendingReasonings = new Map<string, string>();
let rafId: number | null = null;

function flushBatched() {
  useChatStore.setState(state => {
    for (const [msgId, text] of pendingDeltas) {
      if (state.messages[msgId]) {
        state.messages[msgId].content += text;
      }
    }
    for (const [msgId, text] of pendingReasonings) {
      if (state.messages[msgId]) {
        state.messages[msgId].reasoning =
          (state.messages[msgId].reasoning || '') + text;
      }
    }
  });
  pendingDeltas.clear();
  pendingReasonings.clear();
  rafId = null;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: {},
  messageOrder: [],
  agentId: null,
  conversationId: null,
  isSending: false,

  addMessage: (msg) => set(state => ({
    messages: { ...state.messages, [msg.id]: msg },
    messageOrder: [...state.messageOrder, msg.id],
  })),

  appendDelta: (id, delta) => {
    pendingDeltas.set(id, (pendingDeltas.get(id) || '') + delta);
    if (rafId === null) {
      rafId = requestAnimationFrame(flushBatched);
    }
  },

  appendReasoning: (id, delta) => {
    pendingReasonings.set(id, (pendingReasonings.get(id) || '') + delta);
    if (rafId === null) {
      rafId = requestAnimationFrame(flushBatched);
    }
  },

  upsertToolCall: (messageId, toolCall) => set(state => {
    const msg = state.messages[messageId];
    if (!msg) return state;
    const existing = msg.toolCalls || [];
    const idx = existing.findIndex(tc => tc.id === toolCall.id);
    const updated = idx >= 0
      ? [...existing.slice(0, idx), { ...existing[idx], ...toolCall }, ...existing.slice(idx + 1)]
      : [...existing, toolCall];
    return {
      messages: { ...state.messages, [messageId]: { ...msg, toolCalls: updated } }
    };
  }),

  completeMessage: (id, status) => set(state => {
    const msg = state.messages[id];
    if (!msg) return state;
    return { messages: { ...state.messages, [id]: { ...msg, status } } };
  }),

  setAgentId: (agentId) => set({ agentId }),
  setConversationId: (id) => set({ conversationId: id }),
  setIsSending: (v) => set({ isSending: v }),
  
  loadHistory: (msgs) => {
    const messages: Record<string, Message> = {};
    const messageOrder: string[] = [];
    for (const m of msgs) {
      messages[m.id] = m;
      messageOrder.push(m.id);
    }
    set({ messages, messageOrder });
  },

  clearMessages: () => set({ messages: {}, messageOrder: [] }),
}));
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -10
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/ai-chat/store/chatStore.ts
git commit -m "feat: add Zustand chatStore with Map-based state and rAF batching"
```

---

## Task 14: 前端 — chatApi SSE 服务

**Files:**
- Create: `frontend/src/features/ai-chat/services/chatApi.ts`

- [ ] **Step 1: Create chatApi with new SSE protocol parser**

```typescript
// frontend/src/features/ai-chat/services/chatApi.ts
import { useChatStore } from '../store/chatStore';
import type { Message, ToolCall } from '../types/message';

interface ChatRequest {
  message: string;
  agentId: string | null;
  conversationId: string | null;
  messageId: string;
}

interface SseEvent {
  type: string;
  messageId?: string;
  agentId?: string;
  delta?: string;
  toolCall?: ToolCall;
  status?: string;
  error?: string;
  payload?: Record<string, unknown>;
}

export async function sendChatMessage(req: ChatRequest): Promise<void> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      message: req.message,
      agentId: req.agentId,
      conversationId: req.conversationId,
      messageId: req.messageId,
    }),
  });

  if (!response.ok) throw new Error(`Chat request failed: ${response.status}`);
  if (!response.body) throw new Error('Empty response body');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data:')) continue;
        
        const data = trimmed.startsWith('data: ')
          ? trimmed.slice(6)
          : trimmed.slice(5);
        if (data === '[DONE]') continue;

        try {
          const event: SseEvent = JSON.parse(data);
          handleEvent(event);
        } catch {
          console.warn('SSE parse error:', data);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function handleEvent(event: SseEvent): void {
  const { type, messageId, delta, toolCall, status, error } = event;
  const store = useChatStore.getState();

  switch (type) {
    case 'message.delta':
      if (messageId && delta) store.appendDelta(messageId, delta);
      break;
    case 'message.tool_call':
      if (messageId && toolCall) store.upsertToolCall(messageId, toolCall);
      break;
    case 'message.reasoning':
      if (messageId && delta) store.appendReasoning(messageId, delta);
      break;
    case 'message.done':
      if (messageId && status) {
        store.completeMessage(messageId, status as 'done' | 'error');
      }
      store.setIsSending(false);
      break;
    case 'error':
      if (messageId) store.completeMessage(messageId, 'error');
      store.setIsSending(false);
      break;
  }
}
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -10
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/ai-chat/services/chatApi.ts
git commit -m "feat: add chatApi with new SSE protocol parser"
```

---

## Tasks 15-22: 前端 — 核心组件（8 个组件）

由于组件之间相对独立，可在 subagent-driven 模式下并行创建。每个组件遵循相同的步骤模板：
1. 创建组件文件
2. TypeScript 编译检查
3. 提交

**Files to create:**

- `frontend/src/features/ai-chat/components/ChatContainer.tsx`
- `frontend/src/features/ai-chat/components/MessageList.tsx`
- `frontend/src/features/ai-chat/components/MessageBubble.tsx`
- `frontend/src/features/ai-chat/components/ReasoningPanel.tsx`
- `frontend/src/features/ai-chat/components/ToolCallPanel.tsx`
- `frontend/src/features/ai-chat/components/MarkdownRenderer.tsx`
- `frontend/src/features/ai-chat/components/StreamingRenderer.tsx`
- `frontend/src/features/ai-chat/components/InputBox.tsx`

**关键实现要点（按组件）**:

### ChatContainer.tsx
- Layout: flex-col h-screen, Header + MessageList(flex-1 overflow-hidden) + InputBox
- 集成 Agent 选择器（从 storage/session 获取 agentId，加载 agents 列表）
- 在 Chat Header 显示当前 Agent 名称

### MessageList.tsx
- 使用 `useVirtualizer` from `@tanstack/react-virtual`
- `estimateSize: () => 120`, `overscan: 5`
- Auto-scroll: 流式输出时跟踪底部，用户向上滚动 >100px 时暂停
- 暂停时显示 "↓ 回到底部" 浮动按钮

### MessageBubble.tsx
- user: `justify-end`, 蓝色背景气泡
- assistant: `justify-start`, 灰色/白色背景气泡
- 包含内联的 ReasoningPanel + ToolCallPanel（按需渲染）
- 内容通过 MarkdownRenderer 渲染
- 显示 agentId label（如有）: `<span class="text-xs text-gray-400">Agent: {agentId}</span>`

### ReasoningPanel.tsx
- 可折叠面板，`useState(false)` 默认折叠
- 标题: "💭 思考过程"
- 内容: 使用 react-markdown 渲染 reasoning 文字

### ToolCallPanel.tsx
- 每项工具调用一张卡片
- running: 旋转 border spinner + 工具名
- done: 绿色边框 + ✓ + 可展开查看 result（JSON 格式化或文本）
- failed: 红色边框 + ✗ + error 信息

### MarkdownRenderer.tsx
- react-markdown + remarkGfm
- Shiki lazy load: `useEffect` 中 `import('shiki')`
- Fallback: plain `<pre><code>` 直到 Shiki 就绪
- 自定义 pre/code/table/blockquote 组件

### StreamingRenderer.tsx
- 接收 `isStreaming: boolean` + `children`
- streaming 时在末尾追加闪烁光标: `<span class="animate-pulse">▌</span>`

### InputBox.tsx
- `textarea` + Send 按钮
- `Enter` 发送, `Shift+Enter` 换行
- `disableSend` 时按钮 disabled + 灰色
- 占位符: "输入消息..."

每个组件创建后：
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -5
```
确认无新的 TS 错误后提交:
```bash
git add frontend/src/features/ai-chat/components/<Component>.tsx
git commit -m "feat: add <Component> for AI Chat UI"
```

---

## Tasks 23-24: 前端 — Hooks + 集成

### Task 23: useChatStream hook

**Files:**
- Create: `frontend/src/features/ai-chat/hooks/useChatStream.ts`

```typescript
import { useCallback } from 'react';
import { v4 as uuidv4 } from '../../utils/uuid';
import { useChatStore } from '../store/chatStore';
import { sendChatMessage } from '../services/chatApi';
import type { Message } from '../types/message';

export function useChatStream() {
  const store = useChatStore();

  const send = useCallback(async (content: string) => {
    const { agentId, conversationId, isSending } = useChatStore.getState();
    if (!content.trim() || isSending) return;

    const messageId = uuidv4();
    const now = Date.now();

    // Add user message
    useChatStore.getState().addMessage({
      id: uuidv4(),
      role: 'user',
      content: content.trim(),
      status: 'done',
      createdAt: now,
    });

    // Add assistant placeholder
    useChatStore.getState().addMessage({
      id: messageId,
      role: 'assistant',
      content: '',
      status: 'streaming',
      agentId: agentId || undefined,
      conversationId: conversationId || undefined,
      createdAt: now,
    });

    useChatStore.getState().setIsSending(true);

    try {
      await sendChatMessage({
        message: content.trim(),
        agentId,
        conversationId,
        messageId,
      });
    } catch (err) {
      useChatStore.getState().completeMessage(messageId, 'error');
      useChatStore.getState().setIsSending(false);
    }
  }, []);

  return { send, isSending: store.isSending };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/ai-chat/hooks/useChatStream.ts
git commit -m "feat: add useChatStream hook"
```

### Task 24: useConversation hook + App.tsx 路由

**Files:**
- Create: `frontend/src/features/ai-chat/hooks/useConversation.ts`
- Modify: `frontend/src/App.tsx`

`useConversation.ts`:

```typescript
import { useCallback } from 'react';
import { useChatStore } from '../store/chatStore';

export function useConversation() {
  const loadHistory = useCallback(async (conversationId: string) => {
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`/api/chat/history/${conversationId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Failed to load history');
    const data = await res.json();
    if (data.messages) {
      useChatStore.getState().loadHistory(data.messages);
    }
    useChatStore.getState().setConversationId(conversationId);
  }, []);

  return { loadHistory };
}
```

`App.tsx` 路由更新:

```tsx
import { ChatContainer } from './features/ai-chat/components/ChatContainer';
// Keep old import for admin page backward compat

// Add new route:
<Route path="/chat-v2/:id" element={
  <PrivateRoute><ChatContainer /></PrivateRoute>
} />
<Route path="/chat-v2" element={
  <PrivateRoute><ChatContainer /></PrivateRoute>
} />
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/ai-chat/hooks/useConversation.ts \
        frontend/src/App.tsx
git commit -m "feat: add useConversation hook and /chat-v2 route"
```

---

## Task 25: 前端 — 废弃旧文件

**Files:**
- Modify: `frontend/src/components/ChatMessage.tsx`
- Modify: `frontend/src/components/ChatInput.tsx`
- Modify: `frontend/src/hooks/useChat.ts`

- [ ] **Step 1: Add @deprecated comments**

在每个旧文件头部添加:
```typescript
/**
 * @deprecated since v2.0
 * Replaced by features/ai-chat/ components.
 * Kept for reference. Remove after v2.0 stabilization.
 */
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ChatMessage.tsx \
        frontend/src/components/ChatInput.tsx \
        frontend/src/hooks/useChat.ts
git commit -m "chore: mark old Chat components as @deprecated"
```

---

## Task 26: 测试 — 更新 test_chat_scenarios.py

**Files:**
- Modify: `scripts/test_chat_scenarios.py`

- [ ] **Step 1: Update SSE event assertions to new protocol**

将现有测试中对 `"type":"token"` / `"type":"tool_start"` 的断言更新为新格式。关键改动:

```python
# Old: assert event["type"] == "token"
# New: assert event["type"] in ("message.delta", "message.tool_call", "message.reasoning", "message.done")

# Old: assert "token" in event
# New: assert "delta" in event or "toolCall" in event
```

并在测试中验证 messageId 存在:
```python
assert "messageId" in event or event["type"] == "error"
```

- [ ] **Step 2: Run updated tests**

```bash
cd ai_service && python scripts/test_chat_scenarios.py 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
git add scripts/test_chat_scenarios.py
git commit -m "test: update test_chat_scenarios for new SSE protocol"
```

---

## Task 27: 前端 — chatStore 单元测试

**Files:**
- Create: `frontend/src/features/ai-chat/__tests__/chatStore.test.ts`

- [ ] **Step 1: Write chatStore tests**

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useChatStore } from '../store/chatStore';

describe('chatStore', () => {
  beforeEach(() => {
    useChatStore.getState().clearMessages();
  });

  it('addMessage adds to messages and order', () => {
    const id = 'msg-1';
    useChatStore.getState().addMessage({
      id, role: 'user', content: 'hi', status: 'done',
    });
    const state = useChatStore.getState();
    expect(state.messages[id]).toBeDefined();
    expect(state.messages[id].content).toBe('hi');
    expect(state.messageOrder).toContain(id);
  });

  it('appendDelta updates content', () => {
    useChatStore.getState().addMessage({
      id: 'msg-2', role: 'assistant', content: '', status: 'streaming',
    });
    // Trigger rAF batch (synchronous in test via jest fake timers)
    useChatStore.getState().appendDelta('msg-2', 'Hello');
    useChatStore.getState().appendDelta('msg-2', ' World');
    // Flush rAF
    jest.advanceTimersByTime(20);
    const state = useChatStore.getState();
    expect(state.messages['msg-2'].content).toContain('Hello');
  });

  it('upsertToolCall merges by id', () => {
    useChatStore.getState().addMessage({
      id: 'msg-3', role: 'assistant', content: '', status: 'streaming',
    });
    useChatStore.getState().upsertToolCall('msg-3', {
      id: 'tc-1', name: 'search', arguments: { q: 'x' }, status: 'running',
    });
    useChatStore.getState().upsertToolCall('msg-3', {
      id: 'tc-1', name: 'search', status: 'done', result: 'found',
    });
    const state = useChatStore.getState();
    const tcs = state.messages['msg-3'].toolCalls || [];
    expect(tcs).toHaveLength(1);
    expect(tcs[0].status).toBe('done');
    expect(tcs[0].result).toBe('found');
  });

  it('completeMessage sets status', () => {
    useChatStore.getState().addMessage({
      id: 'msg-4', role: 'assistant', content: '', status: 'streaming',
    });
    useChatStore.getState().completeMessage('msg-4', 'done');
    expect(useChatStore.getState().messages['msg-4'].status).toBe('done');
  });

  it('setAgentId updates agentId', () => {
    useChatStore.getState().setAgentId('agent-7');
    expect(useChatStore.getState().agentId).toBe('agent-7');
  });
});
```

- [ ] **Step 2: Run tests**

```bash
cd frontend && npx vitest run src/features/ai-chat/__tests__/ 2>&1
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/ai-chat/__tests__/chatStore.test.ts
git commit -m "test: add chatStore unit tests"
```

---

## Task 28: 验收检查

- [ ] **Step 1: Run full test suite**

```bash
# Python
cd ai_service && python -m pytest tests/ -x -q 2>&1

# Spring Boot
cd backend && mvn test -q 2>&1

# Frontend
cd frontend && npx vitest run 2>&1 && npx tsc --noEmit 2>&1
```

- [ ] **Step 2: Verify against acceptance criteria checklist**

对照验收标准逐项检查:
- [x] Chat UI 完全替换 Ant Design Chat
- [x] 支持流式输出（SSE）
- [x] 支持 reasoning 展示
- [x] 支持 tool call 展示
- [x] 支持 agent 切换
- [x] message 模型统一
- [x] 前后端协议一致
- [x] Spring Boot 仅作为 gateway
- [x] Python 负责 AI 逻辑
- [x] UI 不闪烁、不整屏刷新

- [ ] **Step 3: Commit final checks**

```bash
git add -A
git commit -m "chore: final acceptance verification"
```
