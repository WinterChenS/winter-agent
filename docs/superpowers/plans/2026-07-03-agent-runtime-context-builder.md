# Agent Runtime Context Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

change: `agent-runtime-context-builder`
design-doc: `docs/superpowers/specs/2026-07-03-agent-runtime-context-builder-design.md`

**Goal:** Build a unified backend Context Builder that injects persisted session history into agent runtime prompts while keeping Files / Memory / Knowledge on a shared provider contract as stubs.

**Architecture:** Add a dedicated `ai_service/context/` package for runtime context contracts, provider orchestration, budget trimming, and prompt injection. Integrate the resulting `AgentContext` into the chat entrypoint, graph state, and `AgentFactory` so history is loaded once and reused consistently.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, pytest, psycopg async repository layer

## Global Constraints

- Reuse `db.chat_message_repository.get_messages_by_conversation()` as the session history source.
- Do not change the SSE event protocol or frontend chat message protocol.
- Do not introduce vector DB, RAG, file upload plumbing, or LLM summarization in this change.
- Files / Memory / Knowledge providers must share the same provider contract but may remain stub implementations.
- Keep runtime behavior degradable: provider failures must not block a chat request.

---

### Task 1: Runtime Context Contracts And Provider Skeletons

**Files:**
- Create: `ai_service/context/__init__.py`
- Create: `ai_service/context/models.py`
- Create: `ai_service/context/budget.py`
- Create: `ai_service/context/providers/__init__.py`
- Create: `ai_service/context/providers/base.py`
- Create: `ai_service/context/providers/files.py`
- Create: `ai_service/context/providers/memory.py`
- Create: `ai_service/context/providers/knowledge.py`
- Test: `ai_service/tests/test_context_models.py`

**Interfaces:**
- Produces: `ContextRequest(session_id: str | None, user_query: str, agent_id: str | None, max_tokens: int)`
- Produces: `ContextFragment(provider: str, content: str, tokens: int, priority: int, metadata: dict)`
- Produces: `AgentContext(session_id: str | None, agent_id: str | None, recent_messages: list[dict], fragments: list[ContextFragment], rendered_prompt: str, token_usage: dict[str, int], metadata: dict)`
- Produces: `estimate_text_tokens(text: str) -> int`
- Produces: `trim_text_to_budget(text: str, max_tokens: int) -> str`
- Produces: `class ContextProvider(Protocol): async def collect(self, request: ContextRequest) -> list[ContextFragment]`

- [x] **Step 1: Write the failing contract tests**

```python
from context.models import AgentContext, ContextFragment, ContextRequest
from context.budget import estimate_text_tokens, trim_text_to_budget


def test_context_request_and_fragment_defaults():
    request = ContextRequest(session_id="conv-1", user_query="hello", agent_id="default", max_tokens=400)
    fragment = ContextFragment(provider="session", content="recent history", tokens=2, priority=10, metadata={"source": "db"})
    context = AgentContext(
        session_id="conv-1",
        agent_id="default",
        recent_messages=[{"role": "user", "content": "hello"}],
        fragments=[fragment],
        rendered_prompt="recent history",
        token_usage={"session": 2},
        metadata={"providers": ["session"]},
    )

    assert request.max_tokens == 400
    assert context.fragments[0].provider == "session"
    assert context.metadata["providers"] == ["session"]


def test_budget_helpers_are_deterministic():
    assert estimate_text_tokens("alpha beta gamma") >= 3
    assert trim_text_to_budget("one two three four", max_tokens=2).split() == ["one", "two"]
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_context_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'context'` or missing symbol errors.

- [x] **Step 3: Implement the contracts and stub providers**

```python
# ai_service/context/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ContextRequest:
    session_id: str | None
    user_query: str
    agent_id: str | None
    max_tokens: int


@dataclass(slots=True)
class ContextFragment:
    provider: str
    content: str
    tokens: int
    priority: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentContext:
    session_id: str | None
    agent_id: str | None
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    fragments: list[ContextFragment] = field(default_factory=list)
    rendered_prompt: str = ""
    token_usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

```python
# ai_service/context/budget.py
def estimate_text_tokens(text: str) -> int:
    return len([part for part in text.split() if part.strip()])


def trim_text_to_budget(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    parts = [part for part in text.split() if part.strip()]
    return " ".join(parts[:max_tokens])
```

```python
# ai_service/context/providers/base.py
from __future__ import annotations

from typing import Protocol

from context.models import ContextFragment, ContextRequest


class ContextProvider(Protocol):
    name: str
    priority: int

    async def collect(self, request: ContextRequest) -> list[ContextFragment]:
        ...
```

```python
# ai_service/context/providers/files.py / memory.py / knowledge.py
from context.models import ContextFragment, ContextRequest


class FileContextProvider:
    name = "files"
    priority = 20

    async def collect(self, request: ContextRequest) -> list[ContextFragment]:
        return []


class MemoryContextProvider:
    name = "memory"
    priority = 30

    async def collect(self, request: ContextRequest) -> list[ContextFragment]:
        return []


class KnowledgeContextProvider:
    name = "knowledge"
    priority = 40

    async def collect(self, request: ContextRequest) -> list[ContextFragment]:
        return []
```

- [x] **Step 4: Run the contract tests to verify they pass**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_context_models.py -q`
Expected: PASS with 2 passed.

- [x] **Step 5: Commit (skipped: current session rules prohibit creating commits)**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/context ai_service/tests/test_context_models.py
git commit -m "feat: add runtime context contracts"
```

### Task 2: Session Context Provider

**Files:**
- Create: `ai_service/context/providers/session.py`
- Modify: `ai_service/context/providers/__init__.py`
- Test: `ai_service/tests/test_session_context_provider.py`
- Reference: `ai_service/db/chat_message_repository.py`
- Reference: `ai_service/api/routes/chat.py`

**Interfaces:**
- Consumes: `ContextRequest`
- Consumes: `db.chat_message_repository.get_messages_by_conversation(pool, conversation_id) -> list[dict]`
- Produces: `class SessionContextProvider: async def collect(self, request: ContextRequest) -> list[ContextFragment]`
- Produces: `SessionContextProvider._filter_message(message: dict) -> dict | None`

- [x] **Step 1: Write the failing provider tests**

```python
import pytest

from context.models import ContextRequest
from context.providers.session import SessionContextProvider


@pytest.mark.asyncio
async def test_collect_uses_recent_visible_messages(monkeypatch):
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "Thought: hidden internal step"},
        {"role": "assistant", "content": "这里是最终回答"},
    ]

    async def fake_loader(pool, conversation_id):
        return messages

    monkeypatch.setattr("context.providers.session.get_messages_by_conversation", fake_loader)
    provider = SessionContextProvider(pool=object(), history_limit=5)

    fragments = await provider.collect(ContextRequest("conv-1", "继续", "default", 200))

    assert len(fragments) == 1
    assert "这里是最终回答" in fragments[0].content
    assert "Thought:" not in fragments[0].content


@pytest.mark.asyncio
async def test_collect_returns_empty_without_session_id():
    provider = SessionContextProvider(pool=None, history_limit=5)
    fragments = await provider.collect(ContextRequest(None, "hello", "default", 200))
    assert fragments == []
```

- [x] **Step 2: Run the provider tests to verify they fail**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_session_context_provider.py -q`
Expected: FAIL with `ModuleNotFoundError` or missing `SessionContextProvider`.

- [x] **Step 3: Implement the session provider and filtering**

```python
from __future__ import annotations

import logging

from context.budget import estimate_text_tokens
from context.models import ContextFragment, ContextRequest
from db.chat_message_repository import get_messages_by_conversation

logger = logging.getLogger(__name__)


class SessionContextProvider:
    name = "session"
    priority = 10

    def __init__(self, pool, history_limit: int = 10) -> None:
        self._pool = pool
        self._history_limit = history_limit

    async def collect(self, request: ContextRequest) -> list[ContextFragment]:
        if not request.session_id or not self._pool:
            return []

        messages = await get_messages_by_conversation(self._pool, request.session_id)
        visible = [msg for msg in (self._filter_message(m) for m in messages) if msg is not None]
        recent = visible[-self._history_limit :]
        if not recent:
            return []

        content = "\n".join(f"{msg['role']}: {msg['content']}" for msg in recent)
        return [
            ContextFragment(
                provider=self.name,
                content=content,
                tokens=estimate_text_tokens(content),
                priority=self.priority,
                metadata={"recent_messages": recent},
            )
        ]

    def _filter_message(self, message: dict) -> dict | None:
        content = str(message.get("content") or "").strip()
        if not content or self._is_internal_message(content):
            return None
        return {"role": message.get("role", "assistant"), "content": content}

    def _is_internal_message(self, content: str) -> bool:
        normalized = content.strip()
        return normalized.startswith("Thought:") or normalized.startswith("Action:") or normalized.startswith("Observation:")
```

- [x] **Step 4: Run the provider tests to verify they pass**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_session_context_provider.py -q`
Expected: PASS with 2 passed.

- [x] **Step 5: Commit (skipped: current session rules prohibit creating commits)**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/context/providers ai_service/tests/test_session_context_provider.py
git commit -m "feat: add session context provider"
```

### Task 3: Context Builder, Assembler, And Injector

**Files:**
- Create: `ai_service/context/assembler.py`
- Create: `ai_service/context/injector.py`
- Create: `ai_service/context/builder.py`
- Modify: `ai_service/context/__init__.py`
- Test: `ai_service/tests/test_context_builder.py`

**Interfaces:**
- Consumes: `ContextProvider.collect(request) -> list[ContextFragment]`
- Produces: `assemble_fragments(fragments: list[ContextFragment], max_tokens: int) -> tuple[list[ContextFragment], dict[str, int]]`
- Produces: `render_context_prompt(fragments: list[ContextFragment]) -> tuple[str, dict]`
- Produces: `class ContextBuilder: async def build(self, request: ContextRequest) -> AgentContext`

- [x] **Step 1: Write the failing builder tests**

```python
import pytest

from context.builder import ContextBuilder
from context.models import ContextFragment, ContextRequest


class _Provider:
    def __init__(self, name, priority, fragments):
        self.name = name
        self.priority = priority
        self._fragments = fragments

    async def collect(self, request):
        return self._fragments


@pytest.mark.asyncio
async def test_builder_keeps_high_priority_fragments_when_budget_tight():
    request = ContextRequest("conv-1", "hello", "default", 4)
    session = ContextFragment("session", "one two three", 3, 10, {"recent_messages": []})
    files = ContextFragment("files", "four five six", 3, 20, {})

    builder = ContextBuilder([_Provider("session", 10, [session]), _Provider("files", 20, [files])])
    context = await builder.build(request)

    assert "one two three" in context.rendered_prompt
    assert "four five six" not in context.rendered_prompt


@pytest.mark.asyncio
async def test_builder_returns_empty_context_when_all_providers_empty():
    builder = ContextBuilder([_Provider("session", 10, [])])
    context = await builder.build(ContextRequest(None, "hello", None, 50))
    assert context.rendered_prompt == ""
    assert context.fragments == []
```

- [x] **Step 2: Run the builder tests to verify they fail**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_context_builder.py -q`
Expected: FAIL with missing `ContextBuilder` or missing assembly helpers.

- [x] **Step 3: Implement assembly, injection, and orchestration**

```python
# ai_service/context/assembler.py
from context.budget import trim_text_to_budget
from context.models import ContextFragment


def assemble_fragments(fragments: list[ContextFragment], max_tokens: int):
    ordered = sorted(fragments, key=lambda item: item.priority)
    kept: list[ContextFragment] = []
    token_usage: dict[str, int] = {}
    remaining = max_tokens

    for fragment in ordered:
        if remaining <= 0:
            break
        trimmed = trim_text_to_budget(fragment.content, remaining)
        if not trimmed:
            continue
        trimmed_tokens = min(fragment.tokens, remaining)
        kept.append(ContextFragment(fragment.provider, trimmed, trimmed_tokens, fragment.priority, fragment.metadata))
        token_usage[fragment.provider] = token_usage.get(fragment.provider, 0) + trimmed_tokens
        remaining -= trimmed_tokens

    return kept, token_usage
```

```python
# ai_service/context/injector.py
from context.models import ContextFragment


def render_context_prompt(fragments: list[ContextFragment]) -> tuple[str, dict]:
    if not fragments:
        return "", {"providers": []}

    blocks = [f"[{fragment.provider}]\n{fragment.content}" for fragment in fragments]
    metadata = {
        "providers": [fragment.provider for fragment in fragments],
        "recent_messages": next((fragment.metadata.get("recent_messages", []) for fragment in fragments if fragment.provider == "session"), []),
    }
    return "\n\n".join(blocks), metadata
```

```python
# ai_service/context/builder.py
from context.assembler import assemble_fragments
from context.injector import render_context_prompt
from context.models import AgentContext, ContextRequest


class ContextBuilder:
    def __init__(self, providers):
        self._providers = providers

    async def build(self, request: ContextRequest) -> AgentContext:
        collected = []
        for provider in self._providers:
            try:
                collected.extend(await provider.collect(request))
            except Exception:
                continue

        fragments, token_usage = assemble_fragments(collected, request.max_tokens)
        rendered_prompt, metadata = render_context_prompt(fragments)
        return AgentContext(
            session_id=request.session_id,
            agent_id=request.agent_id,
            recent_messages=metadata.get("recent_messages", []),
            fragments=fragments,
            rendered_prompt=rendered_prompt,
            token_usage=token_usage,
            metadata=metadata,
        )
```

- [x] **Step 4: Run the builder tests to verify they pass**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_context_builder.py -q`
Expected: PASS with 2 passed.

- [x] **Step 5: Commit (skipped: current session rules prohibit creating commits)**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/context ai_service/tests/test_context_builder.py
git commit -m "feat: add context builder pipeline"
```

### Task 4: Integrate Context Builder Into Chat Route And Graph State

**Files:**
- Modify: `ai_service/graph/state.py`
- Modify: `ai_service/api/routes/chat.py`
- Test: `ai_service/tests/test_chat_context_integration.py`
- Reference: `ai_service/graph/multi_agent_graph.py`

**Interfaces:**
- Consumes: `ContextBuilder.build(request) -> AgentContext`
- Produces: new `State` keys `runtime_context_prompt: str | None`, `runtime_context_messages: list[dict]`, `runtime_context_meta: dict | None`
- Produces: helper `_build_runtime_context(pool, conversation_id, active_agent, user_query) -> AgentContext`

- [x] **Step 1: Write the failing integration tests**

```python
import pytest
from fastapi.testclient import TestClient

from main import app


def test_stream_endpoint_builds_runtime_context(monkeypatch):
    captured = {}

    async def fake_build_runtime_context(pool, conversation_id, active_agent, user_query):
        captured["conversation_id"] = conversation_id
        return type("Ctx", (), {
            "rendered_prompt": "[session]\nuser: 历史",
            "recent_messages": [{"role": "user", "content": "历史"}],
            "metadata": {"providers": ["session"]},
        })()

    monkeypatch.setattr("api.routes.chat._build_runtime_context", fake_build_runtime_context)
    client = TestClient(app)
    response = client.post("/api/v1/generate/stream", json={"message": "继续", "conversationId": "conv-ctx-1"})

    assert response.status_code == 200
    assert captured["conversation_id"] == "conv-ctx-1"
```

- [x] **Step 2: Run the integration test to verify it fails**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_chat_context_integration.py -q`
Expected: FAIL with missing `_build_runtime_context` or missing state keys.

- [x] **Step 3: Implement route wiring and state extension**

```python
# ai_service/graph/state.py
class State(TypedDict):
    ...
    runtime_context_prompt: str | None
    runtime_context_messages: list[dict]
    runtime_context_meta: dict | None
```

```python
# ai_service/api/routes/chat.py
from context.builder import ContextBuilder
from context.models import ContextRequest
from context.providers.files import FileContextProvider
from context.providers.knowledge import KnowledgeContextProvider
from context.providers.memory import MemoryContextProvider
from context.providers.session import SessionContextProvider


async def _build_runtime_context(pool, conversation_id, active_agent, user_query):
    builder = ContextBuilder([
        SessionContextProvider(pool=pool, history_limit=10),
        FileContextProvider(),
        MemoryContextProvider(),
        KnowledgeContextProvider(),
    ])
    return await builder.build(ContextRequest(conversation_id, user_query, active_agent, 400))
```

```python
# inside stream_generate
pool_user = get_pool()
runtime_context = await _build_runtime_context(pool_user, trace_ctx.conversation_id, active_agent, request.message)

inputs = {
    "messages": [HumanMessage(content=request.message)],
    "conversation_id": trace_ctx.conversation_id,
    "active_agent": active_agent,
    "runtime_context_prompt": runtime_context.rendered_prompt,
    "runtime_context_messages": runtime_context.recent_messages,
    "runtime_context_meta": runtime_context.metadata,
    ...
}
```

- [x] **Step 4: Run the integration test to verify it passes**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_chat_context_integration.py -q`
Expected: PASS with 1 passed.

- [x] **Step 5: Commit (skipped: current session rules prohibit creating commits)**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/graph/state.py ai_service/api/routes/chat.py ai_service/tests/test_chat_context_integration.py
git commit -m "feat: wire runtime context into chat state"
```

### Task 5: Consume Runtime Context In AgentFactory And Graph Prompts

**Files:**
- Modify: `ai_service/core/agent_factory.py`
- Modify: `ai_service/graph/nodes.py`
- Modify: `ai_service/tests/test_agent_factory.py`
- Create: `ai_service/tests/test_runtime_context_prompting.py`

**Interfaces:**
- Consumes: `AgentContext.rendered_prompt`
- Consumes: graph state keys `runtime_context_prompt`, `runtime_context_messages`, `runtime_context_meta`
- Produces: `AgentFactory.build(definition, context: dict | None = None) -> AgentRuntime` with runtime context aware prompt rendering
- Produces: graph prompt assembly that prepends runtime context before tool observations

- [x] **Step 1: Write the failing prompt-consumption tests**

```python
from core.agent_factory import AgentFactory
from models.agent import AgentDefinition


def test_agent_factory_appends_runtime_context(monkeypatch):
    monkeypatch.setattr("core.agent_factory.get_tool_registry", lambda: None)
    factory = AgentFactory()
    definition = AgentDefinition(name="test", display_name="T", system_prompt="Base prompt")

    runtime = factory.build(definition, context={"runtime_context_prompt": "[session]\nuser: 历史"})

    assert "Base prompt" in runtime.system_prompt
    assert "[session]" in runtime.system_prompt
```

```python
from graph.nodes import agent_node


@pytest.mark.asyncio
async def test_agent_node_includes_runtime_context(monkeypatch):
    captured = {}

    class _LLM:
        async def ainvoke(self, messages):
            captured["system_prompt"] = messages[0].content
            return type("Resp", (), {"content": '{"action": "final_answer", "final_answer": "ok"}'})()

    monkeypatch.setattr("graph.nodes._build_llm", lambda streaming=False, json_mode=True: _LLM())
    monkeypatch.setattr("graph.nodes.get_tool_registry", lambda: None)

    await agent_node({
        "messages": [],
        "active_agent": "default",
        "iteration_count": 0,
        "tool_result": None,
        "runtime_context_prompt": "[session]\nuser: 历史",
    })

    assert "[session]" in captured["system_prompt"]
```

- [x] **Step 2: Run the prompt-consumption tests to verify they fail**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_agent_factory.py tests/test_runtime_context_prompting.py -q`
Expected: FAIL because runtime context is not yet appended to prompts.

- [x] **Step 3: Implement prompt consumption in factory and node assembly**

```python
# ai_service/core/agent_factory.py
    runtime_context_prompt = str(ctx.pop("runtime_context_prompt", "") or "").strip()
    prompt = definition.system_prompt
    for key, value in ctx.items():
        prompt = prompt.replace("{" + key + "}", str(value))
    if runtime_context_prompt:
        prompt = f"{prompt}\n\nRuntime context:\n{runtime_context_prompt}"
```

```python
# ai_service/graph/nodes.py inside agent_node
    runtime_context_prompt = str(state.get("runtime_context_prompt") or "").strip()
    system_lines = [
        _REACT_SYSTEM_PROMPT,
        f"Current server time: {now_str}",
    ]
    if runtime_context_prompt:
        system_lines.append(f"Runtime context:\n{runtime_context_prompt}")
```

- [x] **Step 4: Run the targeted tests plus a narrow regression slice**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_agent_factory.py tests/test_runtime_context_prompting.py tests/test_nodes_prompts.py -q`
Expected: PASS with runtime-context assertions green and existing prompt tests still passing.

- [x] **Step 5: Commit (skipped: current session rules prohibit creating commits)**

```bash
cd /Volumes/work/projects/winter-agent
git add ai_service/core/agent_factory.py ai_service/graph/nodes.py ai_service/tests/test_agent_factory.py ai_service/tests/test_runtime_context_prompting.py
git commit -m "feat: inject runtime context into prompts"
```

### Task 6: Final Verification And Change Hygiene

**Files:**
- Modify: `openspec/changes/agent-runtime-context-builder/tasks.md`
- Reference: `docs/superpowers/specs/2026-07-03-agent-runtime-context-builder-design.md`

**Interfaces:**
- Consumes: all prior task deliverables
- Produces: verified test evidence and updated OpenSpec task checklist

- [x] **Step 1: Mark completed OpenSpec tasks as implementation progresses**

```markdown
- [x] 1.1 新增运行时上下文模型：`ContextRequest`、`ContextFragment`、`AgentContext`
- [x] 2.1 基于 `chat_message_repository` 实现 `SessionContextProvider`
- [x] 3.1 在 `AgentFactory` 接入 Context Builder
```

- [x] **Step 2: Run the focused verification suite**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_context_models.py tests/test_session_context_provider.py tests/test_context_builder.py tests/test_chat_context_integration.py tests/test_agent_factory.py tests/test_runtime_context_prompting.py -q`
Expected: PASS with all runtime-context tests green.

- [x] **Step 3: Run one adjacent regression slice for the touched chat path**

Run: `cd /Volumes/work/projects/winter-agent/ai_service && pytest tests/test_plan_execute_api.py tests/test_multi_agent_graph.py -q`
Expected: PASS, or if environment-dependent tests are skipped, document the skip reason.

- [x] **Step 4: Review the working tree before verify phase**

Run: `cd /Volumes/work/projects/winter-agent && git --no-pager status --short`
Expected: Only intended runtime-context files and task checklist updates are pending.

- [x] **Step 5: Commit the final task batch (skipped: current session rules prohibit creating commits)**

```bash
cd /Volumes/work/projects/winter-agent
git add openspec/changes/agent-runtime-context-builder/tasks.md
git commit -m "chore: finalize agent runtime context builder"
```