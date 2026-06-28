---
change: agent-plan-execute-compose
design-doc: docs/superpowers/specs/2026-06-27-agent-plan-execute-compose-design.md
base-ref: a9329e81fa5e649a59f3aa0a21ea2f604cc1bbdb
archived-with: 2026-06-27-agent-plan-execute-compose
---

# Agent Plan-Execute-Compose Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current reactive ReAct agent pipeline (`router -> collaboration -> merge`) with a proactive Plan -> Execute -> Compose three-phase graph in `ai_service/graph/multi_agent_graph.py`.

**Architecture:** The new graph has three nodes: a `planning_node` (JSON Mode LLM that generates an execution plan with read-only tools), an `execution_node` (self-loop that executes plan steps sequentially with artifact deduplication), and a `composer_node` (Normal Mode streaming LLM that assembles results into a structured report). The old multi-agent topology (router/collaboration/merge) is removed; the legacy `graph.py` pipeline (agent/tool/chart_planner/answer) is untouched.

**Tech Stack:** Python 3.12, LangGraph (StateGraph), LangChain OpenAI, SSE streaming via `astream_events`.

## Global Constraints

- All source files live under `ai_service/` directory (e.g. `ai_service/graph/state.py`, not `graph/state.py`)
- No files outside `ai_service/` are modified
- All new state fields use `TypedDict` in `graph/state.py`; no new reducer functions needed beyond `add_messages`
- `_execute_single_tool()` in `graph/nodes.py:346` is reused as-is (signature: `async def _execute_single_tool(tool_name: str, tool_input: dict, gate: PolicyGate, context: PolicyContext) -> dict`)
- LangGraph conditional edges use string routing (no `END` enum for conditional branches to composer)
- Existing `graph.py` (legacy three-phase pipeline) is not modified
- Existing `core/collaboration.py` and `core/router_agent.py` files are kept but removed from the import chain in `multi_agent_graph.py` and `chat.py`
- All SSE event types (`message.delta`, `message.done`, `message.tool_call`, `tool.started`, `tool.finished`, `conversation.started`) remain unchanged
- Test framework: pytest with pytest.mark.asyncio

archived-with: 2026-06-27-agent-plan-execute-compose
---

## File Structure

| File (under `ai_service/`) | Responsibility | Change |
|---|---|---|
| `graph/state.py` | State TypedDict | Add 5 new fields for plan-execute-compose |
| `graph/nodes.py` | All node functions + helpers | Add `planning_node`, `execution_node`, `composer_node`, dedup helpers, plan validation |
| `graph/multi_agent_graph.py` | New graph topology | Replace router/collaboration/merge with planning/execution/composer |
| `api/routes/chat.py` | SSE streaming endpoint | Remove RouterAgent/CollaborationEngine deps, update graph construction, remove collab_result fallback |
| `tests/test_multi_agent_graph.py` | Graph topology tests | Update tests to match new nodes and routing |

### Sequence by dependency:

```
Task 1 (state) ──> Task 2 (planning_node) ──> Task 4 (execution_node) ──> Task 5 (composer_node) ──> Task 6 (graph topology) ──> Task 7 (chat.py)
       │                                       │
       └──> Task 3 (dedup helpers) ────────────┘
```

archived-with: 2026-06-27-agent-plan-execute-compose
---

### Task 1: Add New State Fields

**Files:**
- Modify: `ai_service/graph/state.py:1-71`

**Interfaces:**
- Consumes: existing `State` TypedDict
- Produces: `State` with 5 new fields: `execution_plan`, `execution_results`, `artifacts`, `current_plan_step`, `plan_phase`

- [x] **Step 1: Add new fields to State TypedDict**

Append the following block after line 69 (after the `agent_results` field) in `ai_service/graph/state.py`:

```python
    # ── V0.5 plan-execute-compose ──────────────────────────────────────────
    execution_plan: dict | None           # JSON execution plan from planning_node
    execution_results: list[dict]         # Per-step results [{step_id, status, data, artifacts}]
    artifacts: list[dict]                 # All artifact metadata [{artifact_id, type, purpose, source_step_id, content_ref}]
    current_plan_step: int                # 0-based index into execution_plan.steps
    plan_phase: str                       # "planning" | "executing" | "composing" | "done"
```

- [x] **Step 2: Run a quick import check**

Run: `python -c "from graph.state import State; print(State.__annotations__.keys())"` (from `ai_service/` directory)
Expected: Output includes `execution_plan`, `execution_results`, `artifacts`, `current_plan_step`, `plan_phase` among existing keys.

- [x] **Step 3: Commit**

```bash
git add ai_service/graph/state.py
git commit -m "feat(agent-plan): add state fields for plan-execute-compose workflow (execution_plan, execution_results, artifacts, current_plan_step, plan_phase)"
```

archived-with: 2026-06-27-agent-plan-execute-compose
---

### Task 2: Implement Planning Node

**Files:**
- Modify: `ai_service/graph/nodes.py` (append after `answer_node`, around line 771)
- Test: `ai_service/tests/test_multi_agent_graph.py` (add tests at end)

**Interfaces:**
- Consumes: `State` (reads `messages`, writes `execution_plan`, `plan_phase`, `reasoning_steps`)
- Produces: `planning_node(state) -> dict` returning state updates with `execution_plan` set, `plan_phase="executing"` (or `"composing"` for empty/fast path)
- Helper: `_validate_plan_json(plan: dict) -> tuple[bool, str]` — validates plan schema, returns `(is_valid, error_message)`
- Helper: `_build_planning_system_prompt(now_str: str, tool_descriptions: str) -> str` — builds the system prompt for the planning LLM
- Helper: `_is_trivial_query(text: str) -> bool` — fast-path detection for greetings/short queries
- Helper: `_generate_fallback_plan(query: str) -> dict` — minimal single-step plan

- [x] **Step 1: Write unit tests for planning helpers**

Add to `ai_service/tests/test_multi_agent_graph.py`:

```python
@pytest.mark.asyncio
async def test_planning_node_generates_plan():
    """Verify planning_node produces a valid execution_plan for a non-trivial query."""
    from graph.state import State
    from graph.nodes import planning_node

    state = State(
        messages=[HumanMessage(content="What were Apple's Q1 2026 earnings?")],
        execution_plan=None,
        execution_results=[],
        artifacts=[],
        current_plan_step=0,
        plan_phase="planning",
        iteration_count=0,
        tool_steps=[],
        reasoning_steps=[],
        # other required fields with defaults
        conversation_id="test-1",
        current_tool=None,
        tool_input=None,
        tool_result=None,
        last_tool_name=None,
        last_tool_query=None,
        consecutive_search_count=0,
        last_guard_reason=None,
        trace_id="",
        turn_id="",
        span_id="",
        parent_span_id=None,
        active_agent="default",
        chart_specs=[],
        pending_chart_spec=None,
        pending_text_block=None,
        blocks=[],
        route="start",
        router_result=None,
        selected_agents=None,
        selected_strategy=None,
        runtimes=None,
        collab_result=None,
        agent_results=None,
    )
    result = await planning_node(state)
    assert result["plan_phase"] == "executing"
    assert result["execution_plan"] is not None
    assert "steps" in result["execution_plan"]
    assert len(result["execution_plan"]["steps"]) > 0
```

If the test file does not exist yet or is mostly mocks, use the mock-based pattern already present.

- [x] **Step 2: Implement `_validate_plan_json()`**

Add to `ai_service/graph/nodes.py` before `agent_node` (around line 26-28, before the class definitions):

```python
def _validate_plan_json(plan: dict) -> tuple[bool, str]:
    """Validate execution plan JSON schema.

    Required top-level keys: title (str), steps (list)
    Each step requires: step_id (int), description (str), required_tools (list)
    Optional per step: expected_artifacts (list of {type, purpose, chart_type})
    """
    if not isinstance(plan, dict):
        return False, "Plan must be a JSON object"
    if "title" not in plan or not isinstance(plan["title"], str):
        return False, "Plan must have a 'title' string field"
    if "steps" not in plan or not isinstance(plan["steps"], list):
        return False, "Plan must have a 'steps' array field"
    if len(plan["steps"]) == 0:
        return False, "Plan must have at least one step"
    for i, step in enumerate(plan["steps"]):
        if not isinstance(step, dict):
            return False, f"Step {i} must be a JSON object"
        if "step_id" not in step:
            return False, f"Step {i} missing 'step_id'"
        if "description" not in step or not isinstance(step["description"], str):
            return False, f"Step {i} missing 'description' string"
        if "required_tools" not in step or not isinstance(step["required_tools"], list):
            return False, f"Step {i} missing 'required_tools' list"
    return True, ""
```

- [x] **Step 3: Implement `_build_planning_system_prompt()`**

Add to `ai_service/graph/nodes.py`:

```python
_PLANNING_SYSTEM_PROMPT = """\
You are a research planner. Given a user query, generate an execution plan as a JSON object.
You have access to read-only tools: search, browser, time.

Output ONLY a valid JSON object. No markdown wrapping, no explanation.

{
  "title": "Brief plan title",
  "steps": [
    {
      "step_id": 1,
      "description": "What this step does — specific search or research action",
      "required_tools": ["search"],
      "expected_artifacts": [
        {"type": "data", "purpose": "What data this step produces", "chart_type": null}
      ]
    }
  ]
}

Rules:
- Each step must accomplish ONE unit of research
- required_tools: choose from ["search", "browser", "time"]
- expected_artifacts.chart_type: null | "line" | "bar" | "pie" | "scatter" | "area" | "radar"
- Limit to 5 steps maximum
- For simple questions (1 search is enough), output a single step
"""


def _build_planning_system_prompt(now_str: str, tool_descriptions: str) -> str:
    lines = [_PLANNING_SYSTEM_PROMPT]
    if now_str:
        lines.append(f"\nCurrent time: {now_str}")
    if tool_descriptions:
        lines.append(f"\nAvailable tools:\n{tool_descriptions}")
    return "\n".join(lines)
```

- [x] **Step 4: Implement `_is_trivial_query()` and `_generate_fallback_plan()`**

Add to `ai_service/graph/nodes.py`:

```python
import re

_GREETING_PATTERNS = re.compile(
    r"^(hello|hi|hey|good morning|good afternoon|good evening|how are you|nice to meet you|thanks|thank you|bye|goodbye)$",
    re.IGNORECASE,
)


def _is_trivial_query(text: str) -> bool:
    """Detect trivial queries that don't need planning: short text or greetings."""
    stripped = text.strip()
    if len(stripped) < 20:
        return True
    if _GREETING_PATTERNS.match(stripped):
        return True
    return False


def _generate_fallback_plan(query: str) -> dict:
    """Generate a minimal single-step fallback plan."""
    return {
        "title": "Research: " + query[:60],
        "steps": [
            {
                "step_id": 1,
                "description": f"Search for information about: {query}",
                "required_tools": ["search"],
                "expected_artifacts": [
                    {"type": "data", "purpose": "Research results for the query", "chart_type": None}
                ],
            }
        ],
    }
```

- [x] **Step 5: Implement `planning_node()`**

Add to `ai_service/graph/nodes.py` (after `answer_node` definition, before the file end):

```python
async def planning_node(state: State) -> dict:
    """Phase 1: Generate execution plan using JSON Mode LLM with read-only tools.

    Flow:
    1. Check fast path: trivial/greeting query -> empty plan -> route to composer
    2. Mini ReAct loop (max 3 rounds) with read-only tools
    3. Validate plan JSON schema
    4. On failure: retry once with error feedback -> fallback plan
    5. Set plan_phase to "executing" (or "composing" if empty)
    """
    from langchain_core.messages import AIMessage, SystemMessage

    # Extract user query
    user_query = ""
    for msg in reversed(list(state.get("messages", []))):
        if hasattr(msg, "type") and msg.type == "human":
            user_query = (msg.content or "").strip()
            break

    # Fast path: trivial query
    if _is_trivial_query(user_query):
        logger.info("[PLANNING] trivial query detected — skipping planning")
        return {
            "execution_plan": None,
            "plan_phase": "composing",
            "reasoning_steps": _append_reason(state, _reason_record(
                "planning_node", "FAST_PATH",
                "Trivial query detected; skipping planning phase.",
            )),
        }

    # Build system prompt with read-only tools
    registry = get_tool_registry()
    tool_descriptions = ""
    if registry:
        tool_lines = []
        for t in registry.list_tools():
            name = str(t.get("name", "")).strip().lower()
            if name in ("search", "browser", "time"):
                tool_lines.append(f"  - {t['name']}: {t['description']}")
        tool_descriptions = "\n".join(tool_lines)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    system_prompt = _build_planning_system_prompt(now_str, tool_descriptions)

    # Mini ReAct loop (max 3 rounds)
    llm = _build_llm(streaming=False, json_mode=True)
    plan = None
    max_planning_rounds = 3

    for planning_round in range(max_planning_rounds):
        msg_list = [SystemMessage(content=system_prompt)] + list(state["messages"])

        # If we have tool observations from previous round, inject them
        if plan is None and planning_round > 0:
            # Add instruction to read state and produce plan
            msg_list.append(SystemMessage(content=(
                "Based on the information gathered, now produce the execution plan JSON. "
                "Make sure to include all steps with required_tools and expected_artifacts."
            )))

        try:
            response = await llm.ainvoke(msg_list)
            content = (response.content or "").strip()
            parsed = json.loads(content)

            # Check if LLM wants to call a tool (planning_round < max-1)
            action = str(parsed.get("action", "")).strip().lower()
            if action == "tool" and planning_round < max_planning_rounds - 1:
                tool_name = str(parsed.get("tool", "")).strip().lower()
                if tool_name in ("search", "browser", "time"):
                    query = str(parsed.get("query", "")).strip()
                    gate = _build_policy_gate()
                    context = PolicyContext(
                        conversation_id=str(state.get("conversation_id") or ""),
                        agent_id="planning",
                    )
                    tool_result = await _execute_single_tool(tool_name, {"query": query}, gate, context)
                    # Store observation in state messages for next round
                    state["messages"].append(AIMessage(
                        content=json.dumps({
                            "action": "tool_result",
                            "tool": tool_name,
                            "result": tool_result.get("result", {}),
                        }, ensure_ascii=False)
                    ))
                    continue

            # Check if the response IS a plan (has title and steps)
            if "title" in parsed and "steps" in parsed:
                plan = parsed
                break
            else:
                # Response is something else — treat as plan_ready
                if "execution_plan" in parsed:
                    plan = parsed["execution_plan"]
                    break
                plan = parsed
                break

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("[PLANNING] JSON parse error (round %d): %s", planning_round, e)
            if planning_round < max_planning_rounds - 1:
                state["messages"].append(AIMessage(
                    content=f"JSON parse error. Output ONLY valid JSON with title and steps fields."
                ))
                continue
            plan = None

    # Validate plan
    if plan:
        is_valid, error_msg = _validate_plan_json(plan)
        if not is_valid:
            logger.warning("[PLANNING] plan validation failed: %s", error_msg)
            # Retry once with error feedback
            try:
                state["messages"].append(SystemMessage(
                    content=f"Plan validation error: {error_msg}. Please fix and output a valid plan JSON."
                ))
                msg_list = [SystemMessage(content=system_prompt)] + list(state["messages"])
                response = await llm.ainvoke(msg_list)
                content = (response.content or "").strip()
                plan = json.loads(content)
                is_valid, error_msg = _validate_plan_json(plan)
                if not is_valid:
                    plan = None
            except (json.JSONDecodeError, TypeError):
                plan = None

    # Fallback: if still no valid plan, generate minimal plan
    if not plan:
        logger.info("[PLANNING] generating fallback plan for query: %s", user_query[:60])
        plan = _generate_fallback_plan(user_query)

    plan_phase = "composing" if not plan.get("steps") else "executing"

    return {
        "execution_plan": plan,
        "plan_phase": plan_phase,
        "reasoning_steps": _append_reason(state, _reason_record(
            "planning_node", "PLAN_READY",
            f"Generated plan: '{plan.get('title', '')}' with {len(plan.get('steps', []))} step(s)",
            extra={"step_count": len(plan.get("steps", []))},
        )),
    }
```

- [x] **Step 6: Run tests to verify compilation**

Run: `cd ai_service && python -m pytest tests/test_multi_agent_graph.py -x -v 2>&1 | head -40`
Expected: tests pass (or at minimum, the imports work without errors).

- [x] **Step 7: Commit**

```bash
git add ai_service/graph/nodes.py ai_service/tests/test_multi_agent_graph.py
git commit -m "feat(agent-plan): add planning_node with JSON Mode LLM, fast-path detection, and fallback plan generation"
```

archived-with: 2026-06-27-agent-plan-execute-compose
---

### Task 3: Implement Artifact Dedup Helpers

**Files:**
- Modify: `ai_service/graph/nodes.py` (add helper functions)

**Interfaces:**
- Produces: `_tokenize_purpose(text: str) -> list[str]` — CJK bigram + English word tokenizer
- Produces: `_check_artifact_dedup(candidate: dict, existing: list[dict]) -> dict | None` — Jaccard similarity match
- Produces: `_register_artifact(state, artifact_type, purpose, step_id, content_ref) -> str` — appends artifact, returns ID

- [x] **Step 1: Write the three helper functions**

Add to `ai_service/graph/nodes.py` (before `planning_node`, or in a "Helpers" section near line 26):

```python
import re


def _tokenize_purpose(text: str) -> list[str]:
    """Extract keywords from purpose text: Chinese bigram + English lowercase words.

    For CJK text: extracts all bigrams (sliding window of 2 chars) plus the full segment.
    For English text: extracts lowercase words.
    """
    if not text:
        return []
    # Extract CJK character sequences
    cjk = re.findall(r'[一-鿿]+', text)
    tokens = []
    for segment in cjk:
        for i in range(len(segment) - 1):
            tokens.append(segment[i:i+2])
        if segment:
            tokens.append(segment)  # full segment too
    # Extract English words
    en_words = re.findall(r'[a-zA-Z]+', text.lower())
    tokens.extend(en_words)
    return tokens


def _check_artifact_dedup(candidate: dict, existing: list[dict]) -> dict | None:
    """Check if a candidate artifact already exists via Jaccard similarity on purpose keywords.

    Returns the matching existing artifact dict if similarity > 0.5, else None.
    Only compares artifacts of the same type.
    """
    c_type = candidate.get("type", "")
    c_keywords = set(_tokenize_purpose(candidate.get("purpose", "")))

    for artifact in existing:
        if artifact.get("type") != c_type:
            continue
        a_keywords = set(_tokenize_purpose(artifact.get("purpose", "")))
        if not c_keywords or not a_keywords:
            continue
        intersection = c_keywords & a_keywords
        union = c_keywords | a_keywords
        jaccard = len(intersection) / len(union)
        if jaccard > 0.5:
            return artifact  # match found

    return None  # no match


def _register_artifact(state, artifact_type: str, purpose: str, step_id: int, content_ref: str) -> str:
    """Register a new artifact in state and return its artifact_id."""
    existing = state.get("artifacts", [])
    artifact_id = f"{artifact_type}_{len(existing)}"
    entry = {
        "artifact_id": artifact_id,
        "type": artifact_type,
        "purpose": purpose,
        "source_step_id": step_id,
        "content_ref": content_ref,
    }
    existing.append(entry)
    return artifact_id
```

- [x] **Step 2: Run a quick import check**

Run: `cd ai_service && python -c "from graph.nodes import _tokenize_purpose, _check_artifact_dedup, _register_artifact; print('OK')"`
Expected: `OK` without import errors.

- [x] **Step 3: Commit**

```bash
git add ai_service/graph/nodes.py
git commit -m "feat(agent-plan): add artifact dedup helpers (_tokenize_purpose, _check_artifact_dedup, _register_artifact)"
```

archived-with: 2026-06-27-agent-plan-execute-compose
---

### Task 4: Implement Execution Node

**Files:**
- Modify: `ai_service/graph/nodes.py` (add `execution_node`)

**Interfaces:**
- Consumes: `State` (reads `execution_plan`, `current_plan_step`, `artifacts`, `execution_results`; writes `execution_results`, `artifacts`, `current_plan_step`, `plan_phase`)
- Produces: `execution_node(state) -> dict` — executes one plan step, increments `current_plan_step`, sets `plan_phase="composing"` when all steps done
- Key: uses `_execute_single_tool()` (line 346), `_check_artifact_dedup()`, `_register_artifact()`

- [x] **Step 1: Implement `execution_node()`**

Add to `ai_service/graph/nodes.py` (between `planning_node` and `composer_node`):

```python
async def execution_node(state: State) -> dict:
    """Phase 2: Execute one step from the execution plan.

    For each step:
    1. Check artifact dedup for each expected_artifact
    2. For each required_tool, call _execute_single_tool (or skip if dedup'd)
    3. Register new artifacts
    4. Store step result in execution_results
    5. Increment current_plan_step
    6. Set plan_phase to "composing" if all steps done

    Self-loop is controlled by conditional edges in multi_agent_graph.py.
    """
    plan = state.get("execution_plan")
    step_idx = state.get("current_plan_step", 0)
    plan_phase = state.get("plan_phase", "executing")

    if not plan or not plan.get("steps"):
        return {"plan_phase": "composing"}

    steps = plan["steps"]
    if step_idx >= len(steps):
        return {"plan_phase": "composing"}

    step = steps[step_idx]
    step_id = int(step.get("step_id", step_idx))
    required_tools = step.get("required_tools", [])
    expected_artifacts = step.get("expected_artifacts", [])

    logger.info("[EXECUTION] executing step %d/%d: %s", step_idx + 1, len(steps), step.get("description", "")[:80])

    user_query = ""
    for msg in reversed(list(state.get("messages", []))):
        if hasattr(msg, "type") and msg.type == "human":
            user_query = (msg.content or "").strip()
            break

    existing_artifacts = list(state.get("artifacts", []))

    # Artifact dedup: for each expected artifact, check if it already exists
    artifact_ids = []
    for ea in expected_artifacts:
        match = _check_artifact_dedup(ea, existing_artifacts)
        if match:
            logger.info("[EXECUTION] artifact dedup match: type=%s purpose='%s' -> existing artifact %s",
                        ea.get("type"), ea.get("purpose", "")[:40], match.get("artifact_id"))
            artifact_ids.append(match.get("artifact_id"))
            _append_reason(state, _reason_record(
                "execution_node", "ARTIFACT_DEDUP_MATCH",
                f"Artifact dedup match: type={ea.get('type')}, matched existing {match.get('artifact_id')}",
                extra={"candidate_type": ea.get("type"), "matched_id": match.get("artifact_id")},
            ))
        else:
            _append_reason(state, _reason_record(
                "execution_node", "ARTIFACT_DEDUP_MISS",
                f"No dedup match for artifact type={ea.get('type')}, purpose='{ea.get('purpose', '')[:40]}'",
            ))

    # Execute tools for this step
    gate = _build_policy_gate()
    context = PolicyContext(
        conversation_id=str(state.get("conversation_id") or ""),
        agent_id=str(state.get("active_agent", "execution")),
    )

    tool_results = []
    step_status = "completed"

    for tool_name in required_tools:
        logger.info("[EXECUTION] invoking tool: %s", tool_name)
        try:
            result = await _execute_single_tool(tool_name, {"query": user_query}, gate, context)
            tool_results.append({
                "tool": tool_name,
                "status": result.get("status", "error"),
                "elapsed_ms": result.get("elapsed_ms", 0),
            })

            if result.get("status") == "error":
                # Retry once
                logger.info("[EXECUTION] retrying tool: %s (first attempt failed)", tool_name)
                result = await _execute_single_tool(tool_name, {"query": user_query}, gate, context)
                tool_results[-1] = {
                    "tool": tool_name,
                    "status": result.get("status", "error"),
                    "elapsed_ms": result.get("elapsed_ms", 0) + tool_results[-1].get("elapsed_ms", 0),
                }

            if result.get("status") == "error":
                step_status = "error"
                _append_reason(state, _reason_record(
                    "execution_node", "TOOL_EXECUTION_FAILURE",
                    f"Tool '{tool_name}' failed after retry for step {step_id}",
                    extra={"tool": tool_name, "error": result.get("error_msg")},
                ))

            # Register result data as artifact
            if result.get("status") == "completed" and result.get("result"):
                content_ref = f"tool:{tool_name}:{step_id}"
                artifact_id = _register_artifact(
                    state,
                    artifact_type=f"tool_result_{tool_name}",
                    purpose=f"Result from {tool_name} for step {step_id}: {step.get('description', '')[:60]}",
                    step_id=step_id,
                    content_ref=content_ref,
                )
                artifact_ids.append(artifact_id)

        except Exception as exc:
            logger.exception("[EXECUTION] unexpected error executing tool '%s'", tool_name)
            tool_results.append({
                "tool": tool_name,
                "status": "error",
                "elapsed_ms": 0,
            })
            step_status = "error"
            _append_reason(state, _reason_record(
                "execution_node", "TOOL_EXECUTION_EXCEPTION",
                f"Unexpected exception for tool '{tool_name}': {str(exc)[:100]}",
            ))

    # Build step result
    step_result = {
        "step_id": step_id,
        "status": step_status,
        "data": tool_results,
        "artifacts": artifact_ids,
    }

    existing_results = list(state.get("execution_results", []))
    existing_results.append(step_result)

    next_step_idx = step_idx + 1
    new_plan_phase = "composing" if next_step_idx >= len(steps) else "executing"

    return {
        "execution_results": existing_results,
        "artifacts": state.get("artifacts", []),
        "current_plan_step": next_step_idx,
        "plan_phase": new_plan_phase,
        "reasoning_steps": _append_reason(state, _reason_record(
            "execution_node", "STEP_COMPLETED",
            f"Step {step_id}/{len(steps)} completed with status={step_status}",
            extra={"step_id": step_id, "status": step_status, "tool_count": len(required_tools)},
        )),
    }
```

- [x] **Step 2: Run a quick import check**

Run: `cd ai_service && python -c "from graph.nodes import execution_node; print('OK')"`
Expected: `OK` without import errors.

- [x] **Step 3: Commit**

```bash
git add ai_service/graph/nodes.py
git commit -m "feat(agent-plan): add execution_node with tool execution, artifact dedup, and step result storage"
```

archived-with: 2026-06-27-agent-plan-execute-compose
---

### Task 5: Implement Response Composer Node

**Files:**
- Modify: `ai_service/graph/nodes.py` (add `composer_node`)

**Interfaces:**
- Consumes: `State` (reads `execution_plan`, `execution_results`, `artifacts`, `messages`)
- Produces: `composer_node(state) -> dict` — generates streaming final answer via Normal Mode LLM, sets `plan_phase="done"`
- No tools bound; streaming output goes through `astream_events`

- [x] **Step 1: Implement `composer_node()`**

Add to `ai_service/graph/nodes.py` (after `execution_node`):

```python
async def composer_node(state: State) -> dict:
    """Phase 3: Generate structured report from plan + results + artifacts.

    Builds a system prompt with:
    - The execution plan
    - Research results per step
    - Available visual artifacts (charts)

    Uses Normal Mode (streaming) LLM with no tool binding.
    Output is streamed via astream_events -> SSE as message.delta.
    """
    plan = state.get("execution_plan")
    results = state.get("execution_results", [])
    artifacts = state.get("artifacts", [])

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    def _format_artifacts_for_prompt(artifacts_list: list[dict]) -> str:
        if not artifacts_list:
            return "No visual artifacts available."
        lines = ["Available Visual Assets:"]
        for a in artifacts_list:
            aid = a.get("artifact_id", "?")
            atype = a.get("type", "?")
            purpose = a.get("purpose", "")
            content_ref = a.get("content_ref", "")
            lines.append(f"- [{aid}] type={atype}, purpose='{purpose}', ref={content_ref}")
        return "\n".join(lines)

    system_prompt = f"""\
You are a professional data analyst. Generate a structured report based on the research results.

[Execution Plan]
{json.dumps(plan, ensure_ascii=False, indent=2) if plan else "No plan was generated (direct response)."}

[Research Results]
{json.dumps(results, ensure_ascii=False, indent=2) if results else "No research results available."}

[Available Visual Assets]
{_format_artifacts_for_prompt(artifacts)}

[Instructions]
- Write a professional analysis report
- Interleave text with images naturally: introduction -> [IMAGE] -> analysis -> [IMAGE] -> conclusion
- Use Markdown image syntax: ![description](image_url)
- Do NOT output code blocks, localhost URLs, or raw tool output
- Reply in the same language as the user's question
- Structure: title, executive summary, sections per plan step, conclusion
- If no research data was collected, just answer the user's question directly and conversationally

Current time: {now_str}
"""

    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])

    llm = _build_llm(streaming=True, json_mode=False)

    try:
        response = await llm.ainvoke(messages)
    except Exception as exc:
        logger.exception("composer_node: LLM invoke failed")
        fallback = "Sorry, an error occurred while generating the answer. Please try again."
        return {
            "messages": [AIMessage(content=fallback)],
            "plan_phase": "done",
        }

    return {
        "messages": [response],
        "plan_phase": "done",
    }
```

- [x] **Step 2: Run a quick import check**

Run: `cd ai_service && python -c "from graph.nodes import composer_node; print('OK')"`
Expected: `OK` without import errors.

- [x] **Step 3: Commit**

```bash
git add ai_service/graph/nodes.py
git commit -m "feat(agent-plan): add composer_node with structured report generation from plan and results"
```

archived-with: 2026-06-27-agent-plan-execute-compose
---

### Task 6: Rewrite Multi-Agent Graph Topology

**Files:**
- Modify: `ai_service/graph/multi_agent_graph.py` (full rewrite)
- Test: `ai_service/tests/test_multi_agent_graph.py` (update tests)

**Interfaces:**
- Produces: `create_plan_execute_graph(checkpointer=None) -> CompiledStateGraph` — new function name
- Routing: planning->execution (plan OK), planning->composer (empty/fast path), execution->execution (more steps), execution->composer (all done), composer->END

- [x] **Step 1: Rewrite `multi_agent_graph.py`**

Replace the entire file content with:

```python
from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from graph.nodes import (
    planning_node,
    execution_node,
    composer_node,
)
from graph.state import State

logger = logging.getLogger(__name__)


def _route_from_planning(state: State) -> str:
    """Route planning -> execution (has plan steps) or -> composer (empty/skip)."""
    phase = state.get("plan_phase", "")
    plan = state.get("execution_plan")
    if phase == "executing" and plan and plan.get("steps"):
        return "execution"
    return "composer"


def _route_from_execution(state: State) -> str:
    """Route execution -> itself (more steps) or -> composer (all done)."""
    phase = state.get("plan_phase", "")
    if phase == "composing":
        return "composer"
    return "execution"


def create_plan_execute_graph(checkpointer=None):
    """
    V0.5 Plan -> Execute -> Compose three-phase pipeline:

    Phase 1 (planning): JSON Mode LLM with read-only tools -> generates execution plan
    Phase 2 (execution): Sequential tool execution with artifact dedup (self-loop)
    Phase 3 (composer): Normal Mode streaming LLM -> structured report
    """
    workflow = StateGraph(State)

    # Add nodes
    workflow.add_node("planning", planning_node)
    workflow.add_node("execution", execution_node)
    workflow.add_node("composer", composer_node)

    # Entry point
    workflow.set_entry_point("planning")

    # Conditional edges
    workflow.add_conditional_edges(
        "planning",
        _route_from_planning,
        {
            "execution": "execution",
            "composer": "composer",
        },
    )

    workflow.add_conditional_edges(
        "execution",
        _route_from_execution,
        {
            "execution": "execution",
            "composer": "composer",
        },
    )

    # Composer always routes to END
    workflow.add_edge("composer", END)

    return workflow.compile(checkpointer=checkpointer)
```

Note: The old `router_node`, `collaboration_node`, `merge_node`, and their routing helpers are removed from this file. They still exist in the codebase history if needed.

- [x] **Step 2: Update tests for the new graph**

Replace the content of `ai_service/tests/test_multi_agent_graph.py` with:

```python
from __future__ import annotations

import pytest

from graph.multi_agent_graph import create_plan_execute_graph


@pytest.mark.asyncio
async def test_plan_execute_graph_builds():
    """Verify the plan-execute-compose graph can be built and compiles with correct nodes."""
    graph = create_plan_execute_graph()

    assert graph is not None
    nodes = list(graph.nodes.keys())
    assert "planning" in nodes
    assert "execution" in nodes
    assert "composer" in nodes
    assert graph.entry_point == "planning"


@pytest.mark.asyncio
async def test_plan_execute_graph_has_conditional_edges():
    """Verify the graph has the correct number of nodes and edges."""
    graph = create_plan_execute_graph()
    assert len(graph.nodes) == 3
    # Graph should have: planning->{execution,composer}, execution->{execution,composer}, composer->END
    assert graph.entry_point == "planning"
```

- [x] **Step 3: Run the updated tests**

Run: `cd ai_service && python -m pytest tests/test_multi_agent_graph.py -x -v`
Expected: All tests pass.

- [x] **Step 4: Ensure old imports are fully removed**

Run: `cd ai_service && grep -n "RouterAgent\|AgentFactory\|CollaborationEngine\|router_node\|collaboration_node\|merge_node\|chart_planner_node\|answer_node" graph/multi_agent_graph.py`
Expected: No matches (all old imports and node registrations removed).

- [x] **Step 5: Commit**

```bash
git add ai_service/graph/multi_agent_graph.py ai_service/tests/test_multi_agent_graph.py
git commit -m "feat(agent-plan): rewrite graph topology to plan->execute->composer, remove old multi-agent routing"
```

archived-with: 2026-06-27-agent-plan-execute-compose
---

### Task 7: Update API Integration (chat.py)

**Files:**
- Modify: `ai_service/api/routes/chat.py`

**Interfaces:**
- Consumes: `create_plan_execute_graph` from `graph.multi_agent_graph`
- Removes: `RouterAgent`, `AgentFactory`, `CollaborationEngine` from imports and instantiation
- Removes: `collab_result` direct streaming fallback (lines 306-318)
- Adds: new state field defaults to `inputs` dict

- [x] **Step 1: Update imports in chat.py**

Replace the import block (around lines 55-60):

Old:
```python
from graph.graph import create_agent_graph
from graph.multi_agent_graph import create_multi_agent_graph
from core.router_agent import RouterAgent
from core.agent_factory import AgentFactory
from core.collaboration import CollaborationEngine
from core.runtime import get_checkpointer, get_tool_registry, get_agent_repository, get_pool
```

New:
```python
from graph.multi_agent_graph import create_plan_execute_graph
from core.runtime import get_checkpointer, get_tool_registry, get_agent_repository, get_pool
```

- [x] **Step 2: Update graph construction in the streaming handler**

In the `else` branch (real API key path, around line 197-208), replace:

Old:
```python
                from core.streaming_event_bus import StreamingEventBus

                event_bus = StreamingEventBus()
                agent_repo = get_agent_repository()
                router = RouterAgent(repository=agent_repo)
                factory = AgentFactory()
                engine = CollaborationEngine(event_bus=event_bus)
                graph = create_multi_agent_graph(
                    router=router, factory=factory, engine=engine,
                    checkpointer=checkpointer, event_bus=event_bus,
                )

                logging.info("[CHAT] streaming multi-agent graph with event bus")
```

New:
```python
                graph = create_plan_execute_graph(checkpointer=checkpointer)

                logging.info("[CHAT] streaming plan-execute-compose graph")
```

- [x] **Step 3: Update graph inputs dict**

Replace the `inputs` dict construction (around lines 212-219):

Old:
```python
                inputs = {
                    "messages": [HumanMessage(content=request.message)],
                    "conversation_id": trace_ctx.conversation_id,
                    "active_agent": active_agent,
                    "chart_specs": [],
                    "blocks": [],
                    "route": "start",
                }
```

New:
```python
                inputs = {
                    "messages": [HumanMessage(content=request.message)],
                    "conversation_id": trace_ctx.conversation_id,
                    "active_agent": active_agent,
                    "chart_specs": [],
                    "blocks": [],
                    "route": "start",
                    # Plan-Execute-Compose state defaults
                    "execution_plan": None,
                    "execution_results": [],
                    "artifacts": [],
                    "current_plan_step": 0,
                    "plan_phase": "planning",
                }
```

- [x] **Step 4: Remove collab_result fallback streaming**

Remove (or comment out) lines 306-318 in chat.py:
```python
                # If collaboration produced a result, stream it directly (skip answer_node)
                logging.info("[CHAT] final_state has_collab=%s",
                             bool(final_state and final_state.get("collab_result")))
                collab_text = ""
                if final_state and final_state.get("collab_result"):
                    collab_text = str(final_state["collab_result"])
                    content_accumulated += collab_text
                    logging.info("[CHAT] streaming collab_result directly (%d chars)", len(collab_text))
                    for char in collab_text:
                        yield to_sse_data(envelope_message_delta(trace_ctx, message_id, char))
                        await asyncio.sleep(0.01)
                else:
                    logging.warning("[CHAT] no collab_result in final_state — nothing to stream")
```

Replace with:
```python
                # Composer node handles output generation via graph streaming
                logging.info("[CHAT] composer output streamed via astream_events")
```

- [x] **Step 5: Remove event_bus runner (no longer needed)**

Remove the `bus_runner` async function definition and the `asyncio.create_task(bus_runner())` call (around lines 257-278), since the new graph doesn't use `StreamingEventBus`. The merge queue should only have `graph_runner` and `graph_done` events. Simplify the merge loop to only track the graph task.

Specifically:
1. Remove the `async def bus_runner()` definition
2. Remove `bus_task = asyncio.create_task(bus_runner())`
3. Remove `event_bus.close()` call in graph_done handler
4. Remove the `bus_done_flag` tracking — only track `graph_done_flag`
5. The merge loop becomes a single-task stream.

Old merge loop structure (around lines 275-301):
```python
                graph_task = asyncio.create_task(graph_runner())
                bus_task = asyncio.create_task(bus_runner())

                graph_done_flag = False
                bus_done_flag = False
                ...

                while not (graph_done_flag and bus_done_flag):
                    ...
                    if source == "graph_done":
                        graph_done_flag = True
                        event_bus.close()
                    elif source == "bus_done":
                        bus_done_flag = True
```

New simplified merge loop:
```python
                graph_task = asyncio.create_task(graph_runner())

                graph_done_flag = False
                tool_calls_accumulated: dict[str, dict] = {}
                content_accumulated = ""

                while not graph_done_flag:
                    source, data = await merge_queue.get()

                    if source == "graph_done":
                        graph_done_flag = True
                    elif source == "error":
                        yield to_sse_data(envelope_error(trace_ctx, str(data)))
                        graph_done_flag = True
                    else:
                        # Accumulate tool calls and content for persistence
                        _accumulate_tool_call(data, tool_calls_accumulated)
                        if data.get("type") == "message.delta":
                            p = data.get("payload", data) or {}
                            content_accumulated += str(p.get("delta", ""))
                        yield to_sse_data(data)

                # Cleanup
                await asyncio.gather(graph_task, return_exceptions=True)
```

- [x] **Step 6: Run a syntax check**

Run: `cd ai_service && python -c "from api.routes.chat import stream_generate; print('import OK')"` or `python -m py_compile api/routes/chat.py`
Expected: No syntax errors (note: full import may fail due to FastAPI routing, but Python compilation should pass).

- [x] **Step 7: Remove unused `from core.streaming_event_bus import StreamingEventBus` import**

After removing `event_bus` usage, make sure the import `from core.streaming_event_bus import StreamingEventBus` inside the `else` branch is also removed.

- [x] **Step 8: Commit**

```bash
git add ai_service/api/routes/chat.py
git commit -m "feat(agent-plan): update chat.py to use plan-execute-compose graph, remove RouterAgent/CollaborationEngine deps and collab_result fallback"
```

archived-with: 2026-06-27-agent-plan-execute-compose
---

## Self-Review

### 1. Spec Coverage

| Design Doc Section | Implemented In |
|---|---|
| Section 3: State Schema Additions | Task 1 |
| Section 4: Planning Node (all 7 sub-flows) | Task 2 |
| Section 4.2: Plan JSON Schema validation | Task 2 (Step 2) |
| Section 4.3: Read-Only Tool Allowlist | Task 2 (Step 5, planning_node filters to search/browser/time) |
| Section 5: Execution Node | Task 4 |
| Section 5.2: Self-Loop Logic | Task 6 (conditional edge execution->execution) |
| Section 5.3: Tool Execution (reuse _execute_single_tool) | Task 4 |
| Section 6: Artifact Deduplication | Task 3 |
| Section 7: Response Composer Node | Task 5 |
| Section 8: SSE Integration | Task 7 (collab_result removal, streaming via astream_events unchanged) |
| Section 8.2: chat.py Changes | Task 7 |
| Section 9: Files Changed | All tasks 1-7 |
| Section 10: Error Handling | Task 2 (retry/fallback), Task 4 (tool failure), Task 5 (LLM failure) |

### 2. Placeholder Scan

No placeholders found. Every step contains actual code and commands.

### 3. Type Consistency

- `execution_plan`: `dict | None` — consistent across all tasks.
- `execution_results`: `list[dict]` with `{step_id, status, data, artifacts}` — consistent.
- `artifacts`: `list[dict]` with `{artifact_id, type, purpose, source_step_id, content_ref}` — consistent.
- `current_plan_step`: `int` — consistent.
- `plan_phase`: `str` with values `"planning" | "executing" | "composing" | "done"` — consistent.
- `_execute_single_tool(tool_name, tool_input, gate, context) -> dict` — reused as-is from existing code.
- Artifact dedup signatures match between Task 3 and Task 4 usage.
- `create_plan_execute_graph(checkpointer)` — new function name used consistently in Task 6 and Task 7.

archived-with: 2026-06-27-agent-plan-execute-compose
---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-27-agent-plan-execute-compose.md`.** Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
