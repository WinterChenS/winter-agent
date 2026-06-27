## 1. State Extension

- [x] 1.1 Add new fields to `State` TypedDict in `graph/state.py`: `execution_plan`, `execution_results`, `artifacts`, `current_plan_step`, `plan_phase`
- [x] 1.2 Initialize new fields in `chat.py` graph inputs with default values

## 2. Planning Node

- [x] 2.1 Implement `planning_node` in `graph/nodes.py`: JSON Mode LLM that generates execution plan, caches plan in `state["execution_plan"]`
- [x] 2.2 Implement plan JSON validation (schema check, step count > 0, required fields present)
- [x] 2.3 Implement retry + fallback logic: JSON parse failure → retry once with error feedback → if still fails, generate minimal single-step plan as fallback
- [x] 2.4 Allow read-only tools (search, browser) in Planning phase; block write-capable tools (chart, sandbox)
- [x] 2.5 Implement greeting/short-query fast path: skip planning for trivial queries

## 3. Execution Node

- [x] 3.1 Implement `execution_node` in `graph/nodes.py`: reads `execution_plan.steps[current_plan_step]`, calls tools per step, stores results in `execution_results`
- [x] 3.2 Implement step result storage: after each step, append `{step_id, status, data, artifacts}` to `state["execution_results"]`
- [x] 3.3 Implement self-loop routing logic: after step N, increment `current_plan_step`; if more steps remain, route back to execution; if all done, route to composer
- [x] 3.4 Implement step tool failure handling: catch errors per step, record error status, continue to next step without aborting

## 4. Artifact Dedup

- [x] 4.1 Implement `_check_artifact_dedup()` function in `graph/nodes.py`: keyword overlap matching on `(type, purpose)` with Jaccard similarity threshold 0.5
- [x] 4.2 Implement `_register_artifact()` function: appends artifact metadata to `state["artifacts"]` with `artifact_id, type, purpose, source_step_id, content_ref`
- [x] 4.3 Integrate dedup check into `execution_node`: before invoking any tool, run `_check_artifact_dedup()`; if match found, skip tool call and reference existing artifact
- [x] 4.4 Log dedup decisions to `state["reasoning_steps"]` with ARTIFACT_DEDUP_MATCH / ARTIFACT_DEDUP_MISS codes

## 5. Response Composer Node

- [x] 5.1 Implement `composer_node` in `graph/nodes.py`: based on existing `answer_node`, receives plan + results + artifacts as context, generates Normal Mode Markdown
- [x] 5.2 Build Composer system prompt: instruct LLM to interleave text and chart references (text → chart → text pattern), use professional report tone, reference artifacts by their purpose
- [x] 5.3 Ensure Composer does NOT invoke any tools (no tool binding)
- [x] 5.4 Set `plan_phase` to "composing" on entry, "done" on completion

## 6. Graph Topology

- [x] 6.1 Modify `create_multi_agent_graph()` in `multi_agent_graph.py`: remove router/collaboration/merge nodes and edges
- [x] 6.2 Add planning/execution/composer nodes to graph
- [x] 6.3 Set entry point to planning, add conditional edges: planning→execution (OK) / planning→composer (plan empty/skip), execution→execution (more steps) / execution→composer (all done), composer→END
- [x] 6.4 Remove unused imports: RouterAgent, AgentFactory, CollaborationEngine from graph construction
- [x] 6.5 Remove `chart_planner_node` and `answer_node` registrations (no longer reachable in new topology)

## 7. API Integration

- [x] 7.1 Update `chat.py` to construct graph with new topology (no RouterAgent, no CollaborationEngine)
- [x] 7.2 Update graph inputs in `chat.py` to include new state fields with default values
- [x] 7.3 Adapt event streaming: ensure `composer_node` output is streamed as `message.delta` SSE events via existing `merge_queue` mechanism
- [x] 7.4 Remove `collab_result` direct streaming fallback (composer handles output now)

## 8. Verification

- [x] 8.1 Manual test: stock analysis query → verify planning generates plan → execution follows steps → composer produces interleaved report
- [x] 8.2 Manual test: simple greeting query → verify fast path skips planning → direct compose
- [x] 8.3 Manual test: verify artifact dedup by requesting overlapping chart types in plan
- [x] 8.4 Manual test: verify plan JSON failure → retry → fallback path works
- [x] 8.5 Verify no regressions: existing SSE event format, message persistence, tool execution
