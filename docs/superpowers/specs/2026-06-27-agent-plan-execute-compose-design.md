---
comet_change: agent-plan-execute-compose
role: technical-design
canonical_spec: openspec
---

# Agent Plan-Execute-Compose Workflow Design

## 1. Overview

将当前被动反应式（Reactive）Agent 执行模式升级为 Plan → Execute → Compose 三阶段，在 `multi_agent_graph.py` 上实现。

**Before**: `router → collaboration(Reactive tool calling) → merge → END`
**After**: `planning → execution(self-loop) → composer → END`

## 2. Graph Topology

```
entry_point("planning")
    │
    ▼
┌──────────────┐      plan OK        ┌──────────────┐
│  planning    │ ──────────────────► │  execution   │◄── self-loop
│              │                     │              │   step N → N+1
│  JSON Mode   │                     │  per step:   │
│  + read-only │                     │  dedup→exec  │
│  tools       │                     │  →store      │
│  (1-3 rounds)│                     │              │
└──────┬───────┘                     └──────┬───────┘
       │ plan_empty                         │ all done
       ▼                                    ▼
┌──────────────┐                     ┌──────────────┐
│  composer    │ ◄────────────────── │  composer    │
│  Normal Mode │                     │  Normal Mode │
│  interleaved │                     │  interleaved │
└──────┬───────┘                     └──────┬───────┘
       │                                    │
       ▼                                    ▼
      END                                  END
```

**Routing conditions**:
| Edge | Condition |
|---|---|
| planning → execution | `plan_phase == "executing"` and `execution_plan.steps` non-empty |
| planning → composer | `plan_phase == "executing"` and `execution_plan.steps` empty (fast path) |
| execution → execution | `current_plan_step < len(plan.steps)` |
| execution → composer | `current_plan_step >= len(plan.steps)` |
| composer → END | unconditional |

## 3. State Schema Additions

New fields in `State` TypedDict (`graph/state.py`):

| Field | Type | Purpose |
|---|---|---|
| `execution_plan` | `dict \| None` | JSON execution plan from planning_node |
| `execution_results` | `list[dict]` | Per-step results `[{step_id, status, data, artifacts}]` |
| `artifacts` | `list[dict]` | All artifact metadata `[{artifact_id, type, purpose, source_step_id, content_ref}]` |
| `current_plan_step` | `int` | 0-based index into plan.steps |
| `plan_phase` | `str` | "planning" → "executing" → "composing" → "done" |

Existing fields preserved (no removal): `messages`, `tool_result`, `tool_steps`, `chart_specs`, `blocks`, `reasoning_steps`, etc.

## 4. Planning Node

### 4.1 Flow

```
planning_node(state):
  1. Extract user query from messages
  2. Check fast path: trivial query (<20 chars, greeting) → empty plan → route composer
  3. Build system prompt with read-only tool definitions (search, browser, time)
  4. Mini ReAct loop (max 3 rounds):
     a. JSON Mode LLM decides: {"action": "tool"/"plan_ready"}
     b. If tool: execute via existing _execute_single_tool, inject Observation
     c. If plan_ready: parse JSON plan, validate schema, exit loop
  5. Validation: check required fields (title, steps[].step_id, description, required_tools)
  6. On failure: retry once with error feedback
  7. Still fails: generate minimal fallback plan (single search step)
  8. Set plan_phase="executing", store execution_plan
```

### 4.2 Plan JSON Schema

```json
{
  "title": "Report Title",
  "steps": [
    {
      "step_id": 1,
      "description": "What this step does",
      "required_tools": ["search"],
      "expected_artifacts": [
        {
          "type": "chart",
          "purpose": "Natural language description of this chart",
          "chart_type": "line"
        }
      ]
    }
  ]
}
```

### 4.3 Read-Only Tool Allowlist

Planning phase binds only: `search`, `browser`, `time`. Chart generation (`generate_chart`), sandbox, and other write-capable tools are NOT bound.

## 5. Execution Node

### 5.1 Flow

```
execution_node(state):
  step_idx = current_plan_step
  step = execution_plan.steps[step_idx]

  1. For each expected_artifact in step.expected_artifacts:
     match = _check_artifact_dedup(expected_artifact, state["artifacts"])
     if match: skip tool call, reference existing artifact
     else: proceed to tool execution

  2. For each tool in step.required_tools:
     result = await _execute_single_tool(tool, query)
     if result.status == "error": retry once
     if still error: record error, continue

  3. Register new artifacts via _register_artifact()

  4. Store step result:
     execution_results.append({
       "step_id": step.step_id,
       "status": "completed" | "error",
       "data": tool_result,
       "artifacts": [artifact_ids]
     })

  5. Increment current_plan_step
```

### 5.2 Self-Loop Logic

Execution node uses LangGraph conditional edge for looping:
- `current_plan_step < len(plan.steps)` → route back to execution
- `current_plan_step >= len(plan.steps)` → set `plan_phase="composing"`, route to composer

Each iteration is one graph step, allowing checkpoint persistence between plan steps.

### 5.3 Tool Execution

Reuses existing `_execute_single_tool()` from `nodes.py:346`:
- PolicyGate evaluation (whitelist, query length, timeout)
- Registry invocation via `registry.invoke_capability()`
- Error normalization
- Step timing (elapsed_ms)

## 6. Artifact Deduplication

### 6.1 Algorithm

```python
def _check_artifact_dedup(candidate: dict, existing: list[dict]) -> dict | None:
    """Jaccard similarity on purpose keywords with type match."""
    c_type = candidate["type"]
    c_keywords = set(_tokenize_purpose(candidate["purpose"]))

    for artifact in existing:
        if artifact["type"] != c_type:
            continue
        a_keywords = set(_tokenize_purpose(artifact["purpose"]))
        if not c_keywords or not a_keywords:
            continue
        intersection = c_keywords & a_keywords
        union = c_keywords | a_keywords
        jaccard = len(intersection) / len(union)
        if jaccard > 0.5:
            return artifact  # match found

    return None  # no match
```

### 6.2 Keyword Tokenization

```python
def _tokenize_purpose(text: str) -> list[str]:
    """Extract keywords: Chinese bigram + English lowercase words."""
    import re
    # Extract CJK characters as bigrams
    cjk = re.findall(r'[一-鿿]+', text)
    tokens = []
    for segment in cjk:
        for i in range(len(segment) - 1):
            tokens.append(segment[i:i+2])
        tokens.append(segment)  # full segment too
    # Extract English words
    en_words = re.findall(r'[a-zA-Z]+', text.lower())
    tokens.extend(en_words)
    return tokens
```

### 6.3 Artifact Registration

```python
def _register_artifact(state, artifact_type, purpose, step_id, content_ref) -> str:
    artifact_id = f"{artifact_type}_{len(state['artifacts'])}"
    state["artifacts"].append({
        "artifact_id": artifact_id,
        "type": artifact_type,
        "purpose": purpose,
        "source_step_id": step_id,
        "content_ref": content_ref,
    })
    return artifact_id
```

## 7. Response Composer Node

### 7.1 Context Construction

```python
system_prompt = f"""\
You are a professional data analyst. Generate a structured report based on the research results.

[Execution Plan]
{json.dumps(plan, ensure_ascii=False, indent=2)}

[Research Results]
{json.dumps(results, ensure_ascii=False, indent=2)}

[Available Visual Assets]
{_format_artifacts_for_prompt(artifacts)}

[Instructions]
- Write a professional analysis report
- Interleave text with images naturally: introduction → [IMAGE] → analysis → [IMAGE] → conclusion
- Use Markdown image syntax: ![description](image_url)
- Do NOT output code blocks, localhost URLs, or raw tool output
- Reply in the same language as the user's question
- Structure: title, executive summary, sections per plan step, conclusion
"""
```

### 7.2 LLM Configuration
- Model: Normal Mode (no JSON mode)
- Streaming: True (streams tokens via astream_events → SSE)
- No tools bound
- Temperature: from settings (default)

## 8. SSE Integration

### 8.1 Event Flow

| Phase | Events |
|---|---|
| Planning started | `plan.started` (optional, for future frontend progress bar) |
| Planning tool calls | `tool.started` / `tool.finished` via existing StreamingEventBus |
| Planning completed | `plan.completed` with plan step count |
| Execution tool calls | `tool.started` / `tool.finished` via existing StreamingEventBus |
| Composer streaming | `message.delta` via graph astream_events |
| Done | `message.done` |

### 8.2 chat.py Changes

Key changes to `stream_generate()`:
1. Remove RouterAgent, AgentFactory, CollaborationEngine instantiation
2. Graph construction: `graph = create_plan_execute_graph(checkpointer=checkpointer)` (new function name or modified `create_multi_agent_graph`)
3. Add new state fields to inputs dict with defaults
4. Remove `collab_result` direct streaming fallback (lines 306-318)
5. Composer's message.delta events flow through existing astream_events → merge_queue → SSE

## 9. Files Changed

| File | Change |
|---|---|
| `graph/state.py` | Add 5 new fields to State TypedDict |
| `graph/nodes.py` | Add planning_node, execution_node, composer_node; add dedup helpers; add plan validation |
| `graph/multi_agent_graph.py` | Remove router/collaboration/merge; add planning/execution/composer nodes and edges; rename function |
| `api/routes/chat.py` | Remove RouterAgent/CollaborationEngine deps; update graph construction; remove collab_result streaming; add state defaults |

**NOT changed**: `graph/graph.py` (legacy), `core/collaboration.py`, `core/router_agent.py` (kept as unused, removed from import chain), `tools/`, `policy/`.

## 10. Error Handling

| Scenario | Behavior |
|---|---|
| Plan JSON parse failure | Retry 1x with error feedback → fallback to minimal plan |
| Tool execution failure | Retry 1x → record error → continue next step |
| LLM call failure (planning/composer) | Return error to user via message.done error event |
| Empty plan (trivial query) | Skip execution, route directly to composer |
| Execution step with no tools | Mark as "noop", continue |
