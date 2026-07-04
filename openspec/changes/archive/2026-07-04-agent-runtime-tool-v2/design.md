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

## Migration Plan

1. 新增 `VersionedTool`、`ToolSchemaAdapter`、增强 `ToolRegistry` — 不影响现有工具
2. 修改 `agent_node` 的 LLM 调用路径（JSON Mode → bind_tools）— 图节点拓扑不变
3. 新增流式工具事件发射 — `tool_node` 内通过 `StreamingEventBus` 推送
4. 部署后监控 tool_calls 成功率，保留回滚到 V1 的能力（通过 feature flag 或配置切换）
