## ADDED Requirements

### Requirement: Runtime Event to SSE Mapping
系统 SHALL 提供 RuntimeEvent 到 SSE EventEnvelope 的适配层。

适配层 MUST 将内部运行时事件转换为前端可消费的 SSE envelope，并保留 trace、conversation、agent、timestamp 等元数据。

#### Scenario: Map tool runtime event
- **WHEN** Event Bus 发布 `tool.invoke` 或 `tool.result` 事件
- **THEN** SSE 适配层输出前端可消费的工具状态事件

#### Scenario: Map graph runtime event
- **WHEN** Event Bus 发布 `graph.enter` 或 `graph.exit` 事件
- **THEN** SSE 适配层输出规范 envelope 或按策略过滤为内部观测事件

### Requirement: Backward Compatible Chat Stream
系统 SHALL 保持现有聊天 SSE 消费路径兼容。

现有前端依赖的 `message.delta`、`message.tool_call`、`message.done`、`image.uploaded` 等事件 MUST 继续可用。

#### Scenario: Existing message delta rendering
- **WHEN** LLM 生成回复文本
- **THEN** 前端仍收到可增量渲染的 `message.delta` 事件

#### Scenario: Existing tool panel rendering
- **WHEN** 工具执行状态通过 RuntimeEvent 进入适配层
- **THEN** 前端工具面板仍能显示运行、完成或失败状态

### Requirement: Stream Merge Ordering
系统 SHALL 在 chat stream 中合并 LangGraph 事件、Event Bus 事件和完成/错误事件。

合并过程 MUST 在单个请求范围内保持事件可读顺序，并在图执行完成后关闭事件流。

#### Scenario: Graph and bus events complete
- **WHEN** LangGraph 执行完成且 Event Bus 已关闭
- **THEN** SSE 流发送最终 `message.done` 并结束

#### Scenario: Graph error during merged stream
- **WHEN** LangGraph 执行期间出现错误
- **THEN** SSE 流发送 error envelope，并执行 Event Bus 清理
