# Comet Design Handoff

- Change: agent-plan-execute-compose
- Phase: design
- Mode: compact
- Context hash: 6f9b8a1ff2ced51334c4ed4d2e012cee50958e63ef2e246356da1151ffdfd76c

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/agent-plan-execute-compose/proposal.md

- Source: openspec/changes/agent-plan-execute-compose/proposal.md
- Lines: 1-32
- SHA256: 5789f7807737962967a54b7315be9014189d33a927f1dbd6f79ab8b0954555df

```md
## Why

当前 Agent 采用被动反应式（Reactive）执行模式：LLM 在每一轮思考时即时决定调用什么 Tool，没有预先规划。这导致 Tool 调用顺序混乱、重复查询、重复生成图片、最终图文结构差。需要将执行范式从「边思考边执行」升级为「先规划、再执行、最后整理」的 Plan → Execute → Compose 三阶段模式，提升 Agent 整体执行质量。

## What Changes

- **新增 Planning Node**：在 Tool 执行前，LLM 首先生成结构化 JSON 执行计划（Execution Plan），计划中明确每个步骤需要的数据、Tool 和预期 Artifact。Planning 阶段允许使用只读 Tool（search、browser）辅助规划，但不生成正文、不生成图表。
- **新增 Execution Node**：严格按 Planning 生成的计划步骤依次执行，每步检查 Artifact 去重后调用 Tool，所有结果（图片、图表、搜索、JSON 等）统一保存到 State，不立即展示。
- **新增 Response Composer Node**：所有 Tool 执行完成后，LLM 根据用户问题 + Planning + Tool Results + Artifacts 统一生成图文自然穿插的专业报告。
- **实现 Artifact 去重机制**：基于 `(artifact_type, purpose_keywords)` 语义相似度进行宽松匹配，避免重复生成图片和重复调用 Tool。
- **简化路由**：移除 Router Agent，用户请求直接进入 Planning 阶段。意图判断的职责由 Planning 的 LLM 在生成计划时自然承担。
- **State 扩展**：新增 `execution_plan`、`execution_results`、`artifacts`、`current_plan_step`、`plan_phase` 字段。

## Capabilities

### New Capabilities

- `agent-execution-plan`: Plan → Execute → Compose 三阶段 Agent 执行工作流。Planning 生成结构化 JSON 计划，Execution 按计划步骤依次执行并去重，Composer 生成图文穿插的最终报告。
- `artifact-dedup`: Artifact 去重机制。基于 artifact type、purpose 的语义相似度进行宽松匹配，执行前检测已有 artifact 并直接引用，避免重复生成。

### Modified Capabilities

- `agent-chat-routing`: 移除 Router Agent 的多 Agent 路由逻辑，改为用户请求直通 Planning 节点。意图判断由 Planning 阶段的 LLM 在生成执行计划时承担。

## Impact

- `ai_service/graph/multi_agent_graph.py` — 主要改动：新增 planning/execution/composer 节点，移除 router→collaboration→merge 流程
- `ai_service/graph/state.py` — 新增 5 个 State 字段
- `ai_service/graph/nodes.py` — 新增 3 个 node 实现 + 去重工具函数
- `ai_service/api/routes/chat.py` — 适配新的 graph 拓扑和 node 输出
- `ai_service/core/router_agent.py` — 不再被主流程引用（保留文件，后续可移除）
- `ai_service/core/collaboration.py` — 不再被主流程引用（保留文件，后续可移除）
```

## openspec/changes/agent-plan-execute-compose/design.md

- Source: openspec/changes/agent-plan-execute-compose/design.md
- Lines: 1-108
- SHA256: 6c2cfa6a3a8b5773f1d56d679730a3209c7835eaba74a95a8abb3f9b17e3a208

[TRUNCATED]

```md
## Context

当前生产图 `multi_agent_graph.py` 的拓扑为 `router → collaboration → merge → END`。`collaboration_node` 内部使用 LangChain 原生 function-calling，LLM 每轮思考即时决定调用什么 Tool（被动反应式），而不是先规划再执行。

遗留图 `graph.py` 有更接近目标的三阶段结构（ReAct → Chart Planner → Answer），但未在生产使用，且其 ReAct 循环同样是反应式的。

核心约束：禁止推翻当前架构、禁止新增复杂 Runtime、禁止多 Agent 协作。

## Goals / Non-Goals

**Goals:**
- 在 `multi_agent_graph.py` 上实现 Plan → Execute → Compose 三阶段
- Planning 生成结构化 JSON 执行计划（允许只读 Tool 辅助）
- Execution 按计划步骤依次执行，含 Artifact 去重
- Composer 生成图文穿插的专业 Markdown 报告
- 尽可能复用现有 `tool_node`、`answer_node` 等代码

**Non-Goals:**
- 不修改 `graph.py`（遗留图）
- 不重构 Tool 系统（`ToolRegistry`、`BaseTool` 保持不变）
- 不修改前端 SSE 协议
- 不新增外部依赖
- 不改造 `PolicyGate` 或 `checkpointer`

## Decisions

### Decision 1: 在 multi_agent_graph.py 内重构拓扑

**选择**：修改 `multi_agent_graph.py`，新增 3 个 node（planning/execution/composer），移除 router→collaboration→merge 流程。

**替代方案**：增强遗留图 `graph.py` 并切换到生产。否决理由：用户明确选择修改生产图，且 `multi_agent_graph.py` 的 `StreamingEventBus` 集成在 `chat.py` 中深度绑定。

**新拓扑**：
```
entry_point("planning")
planning ──(plan OK)──> execution
planning ──(plan failed after retry)──> execution  (降级：单步 plan)

execution ──(more steps)──> execution  (自循环)
execution ──(all done)──> composer

composer ──> END
```

### Decision 2: Planning Node 使用 JSON Mode LLM + 只读 Tool

**选择**：Planning 使用 JSON Mode LLM（`response_format: {"type": "json_object"}`），允许调用 search/browser 只读 Tool，禁止 chart/sandbox 等写入 Tool。Plan 格式错误时重试 1 次，仍失败则降级为单步直接执行。

**替代方案**：Planning 纯推理不调 Tool。否决理由：用户确认允许只读 Tool 辅助规划，提高计划准确性。

**JSON Plan Schema**：
```json
{
  "title": "报告标题",
  "steps": [
    {
      "step_id": 1,
      "description": "步骤描述",
      "required_data": ["需要的数据"],
      "required_tools": ["search"],
      "expected_artifacts": [
        {"type": "chart", "purpose": "图表用途", "chart_type": "line"}
      ]
    }
  ]
}
```

### Decision 3: Execution Node 自循环 + 步进计数

**选择**：Execution Node 使用 graph 条件边自循环，通过 `current_plan_step` 索引追踪进度。每轮执行一个 plan step，完成后 `current_plan_step++` 并循环回 execution，直到所有 step 完成。

**替代方案**：Execution Node 内部一次性 for 循环执行所有 step。否决理由：自循环方式可以利用 LangGraph checkpoint 在每步之间保存状态，便于断点恢复和前端进度展示。

### Decision 4: Artifact 去重采用关键词重叠匹配

**选择**：基于 `(type, purpose_keywords)` 的宽松匹配。预处理：对 purpose 文本做中文分词 + 英文 lowercase → 提取关键词集合 → 与已有 artifact 的 purpose 关键词集合计算 Jaccard 相似度 → 阈值 > 0.5 且 type 相同则判为重复。

**替代方案**：
- 严格 title 匹配：过于严格，漏掉实质重复
```

Full source: openspec/changes/agent-plan-execute-compose/design.md

## openspec/changes/agent-plan-execute-compose/tasks.md

- Source: openspec/changes/agent-plan-execute-compose/tasks.md
- Lines: 1-56
- SHA256: 03be79e5bf80496d0c96a36a9718d96907977300e0dc4756664a3d5c8e35ab8f

```md
## 1. State Extension

- [ ] 1.1 Add new fields to `State` TypedDict in `graph/state.py`: `execution_plan`, `execution_results`, `artifacts`, `current_plan_step`, `plan_phase`
- [ ] 1.2 Initialize new fields in `chat.py` graph inputs with default values

## 2. Planning Node

- [ ] 2.1 Implement `planning_node` in `graph/nodes.py`: JSON Mode LLM that generates execution plan, caches plan in `state["execution_plan"]`
- [ ] 2.2 Implement plan JSON validation (schema check, step count > 0, required fields present)
- [ ] 2.3 Implement retry + fallback logic: JSON parse failure → retry once with error feedback → if still fails, generate minimal single-step plan as fallback
- [ ] 2.4 Allow read-only tools (search, browser) in Planning phase; block write-capable tools (chart, sandbox)
- [ ] 2.5 Implement greeting/short-query fast path: skip planning for trivial queries (< 20 chars or greeting patterns)

## 3. Execution Node

- [ ] 3.1 Implement `execution_node` in `graph/nodes.py`: reads `execution_plan.steps[current_plan_step]`, calls tools per step, stores results in `execution_results`
- [ ] 3.2 Implement step result storage: after each step, append `{step_id, status, data, artifacts}` to `state["execution_results"]`
- [ ] 3.3 Implement self-loop routing logic: after step N, increment `current_plan_step`; if more steps remain, route back to execution; if all done, route to composer
- [ ] 3.4 Implement step tool failure handling: catch errors per step, record error status, continue to next step without aborting

## 4. Artifact Dedup

- [ ] 4.1 Implement `_check_artifact_dedup()` function in `graph/nodes.py`: keyword overlap matching on `(type, purpose)` with Jaccard similarity threshold 0.5
- [ ] 4.2 Implement `_register_artifact()` function: appends artifact metadata to `state["artifacts"]` with `artifact_id, type, purpose, source_step_id, content_ref`
- [ ] 4.3 Integrate dedup check into `execution_node`: before invoking any tool, run `_check_artifact_dedup()`; if match found, skip tool call and reference existing artifact
- [ ] 4.4 Log dedup decisions to `state["reasoning_steps"]` with ARTIFACT_DEDUP_MATCH / ARTIFACT_DEDUP_MISS codes

## 5. Response Composer Node

- [ ] 5.1 Implement `composer_node` in `graph/nodes.py`: based on existing `answer_node`, receives plan + results + artifacts as context, generates Normal Mode Markdown
- [ ] 5.2 Build Composer system prompt: instruct LLM to interleave text and chart references (text → chart → text pattern), use professional report tone, reference artifacts by their purpose
- [ ] 5.3 Ensure Composer does NOT invoke any tools (no tool binding)
- [ ] 5.4 Set `plan_phase` to "composing" on entry, "done" on completion

## 6. Graph Topology

- [ ] 6.1 Modify `create_multi_agent_graph()` in `multi_agent_graph.py`: remove router/collaboration/merge nodes and edges
- [ ] 6.2 Add planning/execution/composer nodes to graph
- [ ] 6.3 Set entry point to planning, add conditional edges: planning→execution (OK) / planning→composer (plan empty/skip), execution→execution (more steps) / execution→composer (all done), composer→END
- [ ] 6.4 Remove unused imports: RouterAgent, AgentFactory, CollaborationEngine from graph construction
- [ ] 6.5 Remove `chart_planner_node` and `answer_node` registrations (no longer reachable in new topology)

## 7. API Integration

- [ ] 7.1 Update `chat.py` to construct graph with new topology (no RouterAgent, no CollaborationEngine)
- [ ] 7.2 Update graph inputs in `chat.py` to include new state fields with default values
- [ ] 7.3 Adapt event streaming: ensure `composer_node` output is streamed as `message.delta` SSE events via existing `merge_queue` mechanism
- [ ] 7.4 Remove `collab_result` direct streaming fallback (composer handles output now)

## 8. Verification

- [ ] 8.1 Manual test: stock analysis query → verify planning generates plan → execution follows steps → composer produces interleaved report
- [ ] 8.2 Manual test: simple greeting query → verify fast path skips planning → direct compose
- [ ] 8.3 Manual test: verify artifact dedup by requesting overlapping chart types in plan
- [ ] 8.4 Manual test: verify plan JSON failure → retry → fallback path works
- [ ] 8.5 Verify no regressions: existing SSE event format, message persistence, tool execution
```

## openspec/changes/agent-plan-execute-compose/specs/agent-chat-routing/spec.md

- Source: openspec/changes/agent-plan-execute-compose/specs/agent-chat-routing/spec.md
- Lines: 1-32
- SHA256: 9ff5f07d3774bc270903915622e944a45798bf91481c0a1e738dbef55fab2c4f

```md
# agent-chat-routing Delta Spec

## MODIFIED Requirements

### Requirement: AgentId-Based Routing
Python AI Service SHALL support an optional `agentId` parameter in chat requests. When `agentId` is present, the system SHALL load the corresponding Agent definition from Agent Repository and inject `active_agent` into LangGraph state. When `agentId` is absent, the system SHALL use the default agent configuration.

The RouterAgent-based multi-agent routing SHALL be removed. User requests SHALL flow directly into the Planning phase of the Plan → Execute → Compose workflow. Intent analysis SHALL be performed by the Planning LLM as part of execution plan generation.

#### Scenario: Request with valid agentId
- **WHEN** `POST /api/v1/generate/stream` request carries `agentId: "search-agent"`
- **THEN** system loads Search Agent definition, injects `active_agent` into graph state, and enters Planning phase

#### Scenario: Request without agentId
- **WHEN** `POST /api/v1/generate/stream` request does not carry agentId
- **THEN** system uses default agent configuration and enters Planning phase directly

#### Scenario: Request with invalid agentId
- **WHEN** `POST /api/v1/generate/stream` request carries non-existent agentId
- **THEN** system returns error event: `{ type: "message.done", status: "error", error: "Agent not found: xxx" }`

## REMOVED Requirements

### Requirement: RouterAgent Multi-Agent Selection
**Reason**: RouterAgent is replaced by Planning LLM's built-in intent analysis. The Plan → Execute → Compose workflow uses a single agent with execution plan-driven tool calls, eliminating the need for multi-agent routing.

**Migration**: All user queries now enter the Planning phase directly. The Planning LLM naturally handles intent analysis as part of plan generation. No user-facing change required.

### Requirement: CollaborationEngine Strategy Execution
**Reason**: CollaborationEngine (sequential/parallel/supervisor strategies) is replaced by plan-driven sequential execution. The execution plan provides explicit ordering, removing the need for runtime strategy selection.

**Migration**: The execution phase follows plan steps sequentially. Parallel tool execution within a single step is preserved via the existing `_parallel_tool_execution` utility.
```

## openspec/changes/agent-plan-execute-compose/specs/agent-execution-plan/spec.md

- Source: openspec/changes/agent-plan-execute-compose/specs/agent-execution-plan/spec.md
- Lines: 1-66
- SHA256: 69c510d0bdd802486f04191302bd510e60aa50c22d9be81638ca6d3232e3572a

```md
# agent-execution-plan Specification

## Purpose
Define the Plan → Execute → Compose three-phase agent execution workflow that replaces the current reactive tool-calling pattern.

## ADDED Requirements

### Requirement: Planning Phase Generates Execution Plan
The system SHALL, upon receiving a user query, first invoke a Planning LLM to generate a structured JSON execution plan before any tool execution. The Planning LLM MAY use read-only tools (search, browser) to gather context but MUST NOT generate charts, final answer text, or invoke write-capable tools.

The execution plan JSON SHALL contain:
- `title`: report title string
- `steps`: ordered list, each step containing `step_id` (integer), `description` (string), `required_data` (string array), `required_tools` (string array), `expected_artifacts` (array of `{type, purpose, chart_type}`)

#### Scenario: User asks for stock analysis
- **WHEN** user inputs "分析最近小米股票走势，并生成合适图表"
- **THEN** Planning LLM generates a JSON execution plan with steps for: market trend analysis (line chart), volume analysis (bar chart), industry comparison, and summary

#### Scenario: Simple factual question
- **WHEN** user inputs "今天天气怎么样"
- **THEN** Planning LLM generates a JSON execution plan with a single search step and no expected artifacts

#### Scenario: Plan JSON parse failure with retry
- **WHEN** Planning LLM outputs non-JSON or malformed JSON
- **THEN** the system retries once with an error feedback prompt
- **AND IF** the retry also fails, the system falls back to direct execution mode (single-step search + compose)

### Requirement: Execution Phase Follows Plan Sequentially
The system SHALL execute plan steps in strict sequential order. For each step, the system SHALL check artifact deduplication before invoking tools. All tool results (text, JSON, images, charts) SHALL be stored in `state["execution_results"]` keyed by `step_id`.

#### Scenario: Sequential step execution
- **WHEN** execution phase begins with a 3-step plan
- **THEN** step 1 executes first, then step 2, then step 3, each building on previous results

#### Scenario: Tool failure in a step
- **WHEN** a tool call in step N fails (timeout, error)
- **THEN** the error is recorded in `execution_results[step_id]` with status "error"
- **AND** execution continues to step N+1

#### Scenario: Step with no required tools
- **WHEN** a plan step has `required_tools: []` and `expected_artifacts: []`
- **THEN** the step is skipped (marked as "noop") and execution proceeds to the next step

### Requirement: Response Composer Generates Structured Final Output
After all execution steps complete, the system SHALL invoke a Composer LLM that receives: the user's original query, the execution plan, all execution results, and all artifacts. The Composer SHALL generate a final Markdown response with analysis text and artifacts naturally interleaved (text → chart → text → chart pattern), not all artifacts then all text.

The Composer LLM SHALL NOT invoke any tools.

#### Scenario: Report with multiple charts
- **WHEN** execution produced 3 chart artifacts and text results
- **THEN** Composer outputs: introduction text → chart reference → analysis → chart reference → analysis → chart reference → conclusion

#### Scenario: Report with no charts
- **WHEN** execution produced only text results with no chart artifacts
- **THEN** Composer outputs a well-structured Markdown text report without chart markers

### Requirement: Plan Phase State Tracking
The system SHALL maintain a `plan_phase` state field that tracks the current phase: "planning", "executing", "composing", or "done". This field SHALL be used for graph routing and error recovery.

#### Scenario: Normal phase progression
- **WHEN** planning completes successfully
- **THEN** `plan_phase` transitions from "planning" to "executing"

#### Scenario: Phase visible in SSE events
- **WHEN** a phase transition occurs
- **THEN** an SSE event is emitted with the new phase for frontend progress indication
```

## openspec/changes/agent-plan-execute-compose/specs/artifact-dedup/spec.md

- Source: openspec/changes/agent-plan-execute-compose/specs/artifact-dedup/spec.md
- Lines: 1-46
- SHA256: a751c0121076df9473001e7b77be8fa213d46c8f2ece723c16e9e28a2b187caf

```md
# artifact-dedup Specification

## Purpose
Define the artifact deduplication mechanism that prevents redundant tool calls and duplicate artifact generation during plan execution.

## ADDED Requirements

### Requirement: Artifact Registration on Creation
The system SHALL register every generated artifact in `state["artifacts"]` with metadata including: `artifact_id`, `type` (chart/image/json/text), `purpose` (natural language description), `source_step_id`, and `content_ref` (path or inline reference). Registration SHALL happen immediately after artifact creation.

#### Scenario: Chart artifact registration
- **WHEN** a line chart "沪深300走势图" is generated in step 1
- **THEN** an artifact record `{artifact_id: "chart_1", type: "chart", purpose: "沪深300走势图", source_step_id: 1, content_ref: "/path/to/chart.png"}` is appended to `state["artifacts"]`

#### Scenario: Text artifact registration
- **WHEN** search results are obtained in step 2
- **THEN** an artifact record `{artifact_id: "search_1", type: "text", purpose: "industry data search results", source_step_id: 2, content_ref: <inline JSON>}` is appended

### Requirement: Semantic Similarity Dedup Check
Before executing any tool call in the execution phase, the system SHALL check `state["artifacts"]` for existing artifacts with matching `type` and semantically similar `purpose`. Matching SHALL use keyword overlap and type equality (loose matching). If a match is found, the existing artifact SHALL be referenced directly without re-executing the tool.

#### Scenario: Exact duplicate chart request
- **WHEN** step 3 requests "沪深300走势图" and step 1 already generated a chart artifact with purpose "沪深300指数近30日走势"
- **THEN** the dedup check matches via keyword overlap (沪深300 + 走势) and type (chart)
- **AND** step 3 skips tool execution and references the existing artifact

#### Scenario: Non-duplicate request
- **WHEN** step 2 requests "成交量柱状图" and no existing artifact has matching keywords
- **THEN** the dedup check finds no match
- **AND** the tool executes normally

#### Scenario: Different type, similar purpose
- **WHEN** step N requests a "chart" for "industry data" and an existing artifact has type "text" with purpose containing "industry data"
- **THEN** the dedup check does NOT match (different types)
- **AND** the tool executes normally

### Requirement: Dedup Match Logging
The system SHALL record dedup decisions in `state["reasoning_steps"]` with the decision (matched or not), the matched artifact_id if applicable, and the similarity score or rationale.

#### Scenario: Dedup match logged
- **WHEN** a dedup match is found
- **THEN** a reasoning step `{node: "execution_node", code: "ARTIFACT_DEDUP_MATCH", message: "Skipping step 3: matched existing artifact chart_1"}` is recorded

#### Scenario: Dedup miss logged
- **WHEN** no dedup match is found
- **THEN** a reasoning step `{node: "execution_node", code: "ARTIFACT_DEDUP_MISS", message: "No existing artifact matched for step 2"}` is recorded
```

