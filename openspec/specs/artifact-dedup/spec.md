# artifact-dedup Specification

## Purpose
TBD - created by archiving change agent-plan-execute-compose. Update Purpose after archive.
## Requirements
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

