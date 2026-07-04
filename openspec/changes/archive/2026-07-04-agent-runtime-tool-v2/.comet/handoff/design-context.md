# Comet Design Handoff

- Change: agent-runtime-tool-v2
- Phase: design
- Mode: compact
- Context hash: 063cebca13c84be7694967fb603b5bad156db6ab822a96363ef4e39cfdbc7c89

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/agent-runtime-tool-v2/proposal.md

- Source: openspec/changes/agent-runtime-tool-v2/proposal.md
- Lines: 1-33
- SHA256: c9d199f913d79cefd5d5d1c567d69698fcd998e66e957341f9a57e9852f045e5

```md
## Why

当前 Agent Runtime 的 Tool Runtime v1 基于 JSON Mode 文本解析 ReAct 循环实现工具调用，存在 JSON 解析失败风险和 Provider 锁定问题。V0.7 Context Builder 已就绪，需要在此基础上升级工具运行时：引入 LLM 原生 tool_calls 机制消除解析脆弱性，补齐 Schema 版本管理、流式工具结果、Tool Metrics 等完整工具运行时能力，为后续多 Provider（Anthropic/Ollama）扩展做好准备。

## What Changes

- **BREAKING**: `agent_node` 从 JSON Mode 文本解析切换为 LLM 原生 `bind_tools` 调用，路由逻辑重新设计
- 新增 `ToolSchemaVersion` 数据模型，支持工具定义的语义版本管理和向后兼容
- `ToolRegistry` 增强：新增 lifecycle hooks（pre/post execute）、Tool Metrics 统计、动态注册/注销
- 新增 `ToolSchemaAdapter`，支持 OpenAI/Anthropic 多 Provider 工具 schema 转换
- 工具执行结果通过 `StreamingEventBus` 流式输出（`tool.progress` / `tool.output` / `tool.completed` SSE 事件）
- 并行工具执行补全 per-tool 独立超时控制
- ReAct system prompt 重写：不再要求 JSON 格式输出，改为引导 LLM 正确使用 tool_calls

## Capabilities

### New Capabilities

- `tool-runtime-v2`: 原生 tool_calls 工具运行时，替代 JSON Mode 文本解析，包含 Schema 版本管理、流式工具结果、Tool Metrics、多 Provider 适配

### Modified Capabilities

<!-- 本次不修改已有 capability spec -->

## Impact

- `ai_service/graph/nodes.py` — agent_node 重构（JSON 解析 → tool_calls 路由）
- `ai_service/tools/` — ToolRegistry 增强、Schema 版本化、Provider 适配器
- `ai_service/core/collaboration.py` — 接入流式工具事件
- `ai_service/api/events/event_mapper.py` — 新增 tool.progress/output 事件映射
- `ai_service/domain/event_envelope.py` — 新增流式工具事件 envelope
- `ai_service/core/streaming_event_bus.py` — 复用现有侧通道
- 前端不改动（现有 SSE 处理已兼容 tool 事件类型）
```

## openspec/changes/agent-runtime-tool-v2/design.md

- Source: openspec/changes/agent-runtime-tool-v2/design.md
- Lines: 1-86
- SHA256: 5b1bed9b03f6aa04a854be24a11cbe007ac873284f53771f443fda657cd85dd0

[TRUNCATED]

```md
## Context

当前 Agent Runtime 的 Tool Runtime v1 通过 JSON Mode (`response_format: {"type": "json_object"}`) 引导 LLM 输出结构化 JSON 来实现工具调用路由。`agent_node` 解析 LLM 文本输出中的 `action` 字段决定进入 tool_node 还是 chart_planner。这种方式在绝大多数场景可工作，但存在根本性限制：

1. **解析脆弱性**：JSON 解析失败时直接触发 `_force_final_answer`，用户看到的是兜底响应而非预期结果
2. **Provider 锁定**：JSON Mode 和 prompt engineering 依赖 OpenAI 特有行为，无法平滑迁移到 Anthropic/Ollama
3. **能力天花板**：无法利用 LLM 原生 parallel tool calling、结构化 tool_calls 响应等能力

V0.7 Context Builder 已通过 `graph/nodes.py` 注入运行时上下文。本设计在此基础上替换工具调用机制，引入：
- LLM 原生 `bind_tools` 替代 JSON Mode 文本解析
- ToolSchema 版本管理
- 流式工具结果通过已有 `StreamingEventBus` 侧通道
- Tool Metrics 可观测性

## Goals / Non-Goals

**Goals:**
- agent_node 使用 `llm.bind_tools(tools)` 发起工具调用，移除 JSON Mode 依赖
- ToolRegistry 支持 lifecycle hooks、metrics、动态注册
- ToolSchema 语义版本管理（major.minor.patch），支持多版本共存和迁移
- 工具执行进度通过 `StreamingEventBus` 实时推送 SSE 事件
- 多 Provider（OpenAI/Anthropic）schema 自动适配

**Non-Goals:**
- 不新增工具类型（search/browser/time/sandbox 保持不变）
- 不改动前端 SSE 解析逻辑（已有 tool.started/finished/failed 处理）
- 不改变 ReAct 图的节点拓扑（agent_node → tool_node → agent_node 不变）
- 不引入 LangChain 之外的 LLM 框架
- 不修改 chat message protocol 或 SSE envelope schema version

## Decisions

### Decision 1: 使用 LangChain `bind_tools` 而非手写 API 调用

**选择**: `llm.bind_tools([tool.to_openai_schema() for tool in tools])`

**备选**: 手动构造 OpenAI/Anthropic HTTP API 请求

**理由**: 项目已深度使用 LangChain（ChatOpenAI、graph、checkpointer），`bind_tools` 是 LangChain 标准路径，自动处理 tool_calls 注入和 ToolMessage 响应解析。手动 API 请求会引入额外的 HTTP 层和错误处理复杂度，与现有 LangGraph 流式架构不兼容。

### Decision 2: 路由判断从 JSON `action` 字段改为 tool_calls 存在性

**当前**: LLM 返回 `{"action": "tool", "tool": "search", ...}` → agent_node 解析路由
**新方案**: LLM 返回 `AIMessage(tool_calls=[...])` → 有 tool_calls 进 tool_node，无 tool_calls 进 chart_planner

**备选**: 保留 JSON 输出作为 fallback，tool_calls 优先

**理由**: `bind_tools` 模式下 LLM 响应已经包含明确的 `tool_calls` 列表，不需要额外的 action 字段做路由判断。保留 JSON fallback 会增加两份代码路径和测试矩阵。

### Decision 3: Schema 版本管理使用 semver + compatible check

**选择**: `ToolSchemaVersion(version="1.0.0", parameters=..., deprecated_params=[...], migration_note=...)`

**备选**: 简单递增整数版本号

**理由**: semver 提供明确的 breaking change 信号（major bump）和 backward-compatible 信号（minor/patch），与工具消费者（前端、其他 agent）的兼容性预期对齐。

### Decision 4: 流式事件复用 StreamingEventBus + 新增事件类型

**选择**: 在 `StreamingEventBus` 上新增 `tool.progress` / `tool.output` / `tool.completed` 事件类型

**备选**: 通过 LangGraph streaming events 直接映射（已有 `map_langgraph_event_to_envelopes`）

**理由**: LangGraph 的 `astream_events` 已经是主要流式通道，但图节点内部的工具执行进度（如 sandbox 执行时间长的场景）无法通过 LangGraph event 表达。`StreamingEventBus` 作为侧通道已经在 `collaboration.py` 中使用，直接复用即可。

### Decision 5: Per-tool 超时在 `_execute_single_tool` 中原生支持

**选择**: 在 `BaseTool` 上已有的 `timeout_ms` 字段上做超时控制，`_execute_single_tool` 使用 `asyncio.wait_for`

**备选**: 全局超时配置

**理由**: 工具执行时间差异大（browser 可能需要 10s+，time 只要 10ms），全局超时无法适配。`BaseTool` 已定义 `timeout_ms` 字段但未被实际使用，直接激活即可。

## Risks / Trade-offs

- **[Provider 兼容性]** `bind_tools` 在不同 Provider 上的 tool calling 格式有差异 → Mitigation: `ToolSchemaAdapter` 提供 OpenAI/Anthropic 双向转换
- **[路由逻辑回退]** 移除 JSON fallback 后，如果 LLM 不遵循 tool_calls 协议，可能空转 → Mitigation: 保留 `_force_final_answer` 作为兜底，但触发条件从 JSON parse error 改为 "空 tool_calls + 不包含有效回答"
- **[ReAct prompt 重写]** 移除 JSON 格式约束后 LLM 行为可能变化 → Mitigation: 新 prompt 明确引导 tool_calls 的使用时机和 final_answer 条件，通过测试覆盖
- **[已有工具兼容]** `BaseTool.input_schema` 已被 V1 工具使用 → Mitigation: 不改 `BaseTool` 接口，新增 `VersionedTool` mixin 供需要版本管理的工具继承

```

Full source: openspec/changes/agent-runtime-tool-v2/design.md

## openspec/changes/agent-runtime-tool-v2/tasks.md

- Source: openspec/changes/agent-runtime-tool-v2/tasks.md
- Lines: 1-43
- SHA256: 21439b0b7b66fcc41624af841e7a8619f6922d5c860ae7b51f4ef90171193784

```md
## 1. Native Tool Calling — bind_tools Migration

- [ ] 1.1 新增 `ToolSchemaAdapter`：实现 OpenAI/Anthropic 工具 schema 双向转换
- [ ] 1.2 在 `agent_node` 中集成 `llm.bind_tools()`，移除 JSON Mode 依赖
- [ ] 1.3 重新设计路由逻辑：基于 `AIMessage.tool_calls` 存在性判断 tool/chart_planner
- [ ] 1.4 重写 `_REACT_SYSTEM_PROMPT`：移除 JSON 格式约束，改为 tool_calls 使用引导
- [ ] 1.5 保留 JSON Mode fallback 路径（Provider 不支持 tool_calls 时自动降级）

## 2. Schema Version Management

- [ ] 2.1 新增 `ToolSchemaVersion` 数据模型（version、parameters、deprecated_params、migration_note）
- [ ] 2.2 新增 `VersionedTool` mixin/基类，支持多版本 schema 注册和查询
- [ ] 2.3 实现兼容性校验：检查调用参数是否与目标 schema 版本兼容
- [ ] 2.4 为 `TimeTool` 添加多版本 schema 示例（验证版本管理流程）
- [ ] 2.5 写入版本化工具调用的事件追踪（记录 schema_version 到 tool_steps）

## 3. Streaming Tool Results

- [ ] 3.1 在 `tool_node` 中注入 `StreamingEventBus`，支持发射 `tool.progress` 事件
- [ ] 3.2 新增 `tool.output` 和 `tool.completed` SSE 事件类型到 `event_envelope.py`
- [ ] 3.3 在 `event_mapper.py` 中新增 `tool.progress`/`tool.output`/`tool.completed` 映射
- [ ] 3.4 为 `CodeSandboxTool` 添加流式输出能力（验证 streaming path）
- [ ] 3.5 确保流式事件不影响 tool_steps 持久化和最终结果聚合

## 4. Parallel Execution — Per-tool Timeout

- [ ] 4.1 在 `_execute_single_tool` 中激活 `BaseTool.timeout_ms` 超时控制（asyncio.wait_for）
- [ ] 4.2 超时结果 SHALL 包含 `TOOL_TIMEOUT` 错误码且不影响其他并行工具结果
- [ ] 4.3 确保 `_parallel_tool_execution` 的 asyncio.gather 在部分超时场景下正确合并

## 5. Tool Metrics

- [ ] 5.1 在 `ToolRegistry` 中新增 metrics 存储：invoke_count、total_latency_ms、error_count
- [ ] 5.2 在 `tool_node` 和 `_execute_single_tool` 中记录每次调用的耗时和状态
- [ ] 5.3 新增 `ToolRegistry.get_metrics(name: str) -> ToolMetrics` 查询接口
- [ ] 5.4 新增 `tool_summary` SSE 事件，在流结束后推送本轮所有工具调用统计

## 6. Migration, Compatibility, and Final Verification

- [ ] 6.1 确保现有所有工具（search/browser/time/sandbox）在 bind_tools 模式下正常执行
- [ ] 6.2 运行全部现有测试套件确认无回归
- [ ] 6.3 新增集成测试：bind_tools 路径 + JSON fallback 路径 + 流式工具事件路径
- [ ] 6.4 更新 roadmap V0.6 文档状态为已完成
```

## openspec/changes/agent-runtime-tool-v2/specs/tool-runtime-v2/spec.md

- Source: openspec/changes/agent-runtime-tool-v2/specs/tool-runtime-v2/spec.md
- Lines: 1-64
- SHA256: 68b52c37134cb462cd826542195bba912f97696e334ef0f07b40fb3d33202972

```md
## ADDED Requirements

### Requirement: Agent Runtime SHALL use native LLM tool_calls for tool invocation
The `agent_node` SHALL bind registered tools to the LLM using `bind_tools` and route execution based on the presence of `tool_calls` in the LLM response, instead of parsing JSON text.

#### Scenario: LLM returns tool_calls
- **WHEN** the LLM response contains one or more `tool_calls`
- **THEN** the agent_node SHALL route to the tool_node with the structured tool call data

#### Scenario: LLM returns no tool_calls
- **WHEN** the LLM response contains no `tool_calls` and the agent has collected evidence
- **THEN** the agent_node SHALL route to chart_planner for final answer generation

#### Scenario: bind_tools not supported by provider
- **WHEN** the configured LLM provider does not support native tool calling
- **THEN** the runtime SHALL fall back to the existing JSON Mode path or raise a clear configuration error

### Requirement: Tool schemas SHALL support semantic versioning
Each tool definition SHALL support versioned schemas with backward compatibility checking.

#### Scenario: multiple schema versions coexist
- **WHEN** a tool has both v1.0.0 and v2.0.0 schemas registered
- **THEN** the runtime SHALL serve the latest version by default and allow callers to request a specific version

#### Scenario: deprecated parameter in new version
- **WHEN** a schema version marks a parameter as deprecated
- **THEN** the runtime SHALL accept calls using the deprecated parameter and include a deprecation warning

### Requirement: Tool execution results SHALL stream real-time progress via SSE
The tool_node SHALL emit streaming progress events through the StreamingEventBus for long-running tool executions.

#### Scenario: tool execution with progress
- **WHEN** a tool supports streaming progress updates
- **THEN** the SSE stream SHALL emit `tool.progress` and `tool.output` events before the final `tool.completed` event

#### Scenario: tool completes without streaming support
- **WHEN** a tool does not support streaming (legacy or fast-executing)
- **THEN** the SSE stream SHALL emit only `tool.completed` with the execution result

#### Scenario: legacy tool without execute_stream
- **WHEN** a tool only implements `execute()` without overriding `execute_stream()`
- **THEN** the tool_node SHALL automatically emit `tool.started` before execution and `tool.completed` after execution, maintaining backward compatibility

### Requirement: ToolRegistry SHALL support lifecycle hooks and metrics
The ToolRegistry SHALL provide pre/post-execution hooks and collect per-tool invocation metrics.

#### Scenario: pre-execution hook
- **WHEN** a pre-execution hook is registered for a tool
- **THEN** the hook SHALL execute before the tool's `execute` method, and SHALL be able to modify or reject the input

#### Scenario: metrics collection
- **WHEN** a tool is invoked
- **THEN** the registry SHALL record invocation count, execution latency, and error status for later querying

### Requirement: Tool schemas SHALL adapt to multiple LLM providers
The ToolSchemaAdapter SHALL convert tool definitions between OpenAI and Anthropic formats.

#### Scenario: OpenAI format tool schema
- **WHEN** the active LLM provider is OpenAI-compatible
- **THEN** the adapter SHALL output `{"type": "function", "function": {"name": "...", "parameters": {...}}}` format

#### Scenario: Anthropic format tool schema
- **WHEN** the active LLM provider is Anthropic
- **THEN** the adapter SHALL output Anthropic-native tool use format with `name`, `description`, `input_schema`
```

