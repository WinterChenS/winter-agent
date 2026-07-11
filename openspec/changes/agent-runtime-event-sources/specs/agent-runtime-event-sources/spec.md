## ADDED Requirements

### Requirement: LLM Lifecycle Events
系统 SHALL 在 LLM 调用边界发布标准运行时事件。

LLM 调用开始 MUST 发布 `llm.request`，调用成功 MUST 发布 `llm.response`，调用失败 MUST 发布 `llm.error`。

#### Scenario: Successful LLM call
- **WHEN** Agent Runtime 发起一次 LLM 调用并成功返回
- **THEN** Event Bus 依次收到 `llm.request` 和 `llm.response` 事件

#### Scenario: Failed LLM call
- **WHEN** LLM 调用抛出异常或返回不可恢复错误
- **THEN** Event Bus 收到包含错误摘要的 `llm.error` 事件

### Requirement: Tool Lifecycle Events
系统 SHALL 在工具调用全生命周期发布标准运行时事件。

工具开始 MUST 发布 `tool.invoke`，可观测进度 MUST 发布 `tool.progress`，成功 MUST 发布 `tool.result`，失败 MUST 发布 `tool.error`。

#### Scenario: Successful tool call
- **WHEN** 工具被调用并成功返回结果
- **THEN** Event Bus 至少收到 `tool.invoke` 和 `tool.result` 事件

#### Scenario: Tool progress
- **WHEN** 工具执行期间产生进度或流式输出
- **THEN** Event Bus 收到 `tool.progress` 事件且包含工具名、调用 ID 和进度负载

#### Scenario: Failed tool call
- **WHEN** 工具执行失败
- **THEN** Event Bus 收到 `tool.error` 事件且包含错误码或错误摘要

### Requirement: Graph Node Lifecycle Events
系统 SHALL 在 LangGraph 节点执行边界发布标准运行时事件。

节点进入 MUST 发布 `graph.enter`，节点成功退出 MUST 发布 `graph.exit`，节点异常 MUST 发布 `graph.error`。

#### Scenario: Graph node success
- **WHEN** planning、execution 或 composer 节点完成执行
- **THEN** Event Bus 收到对应节点的 `graph.enter` 和 `graph.exit` 事件

#### Scenario: Graph node failure
- **WHEN** 任一图节点执行异常
- **THEN** Event Bus 收到 `graph.error` 事件且主错误处理路径保持原有行为

### Requirement: Event Source Failure Isolation
系统 SHALL 隔离事件发布失败与业务执行失败。

事件发布失败 MUST 不改变原有 LLM、工具或图节点的业务结果。

#### Scenario: Event publishing fails during tool execution
- **WHEN** 工具执行成功但事件发布失败
- **THEN** 工具结果仍按原有路径返回，事件发布错误被记录或降级处理
