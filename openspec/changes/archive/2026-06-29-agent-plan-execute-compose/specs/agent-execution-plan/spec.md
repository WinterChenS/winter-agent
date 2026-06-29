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
