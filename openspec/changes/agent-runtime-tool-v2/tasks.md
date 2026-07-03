## 1. Native Tool Calling — bind_tools Migration

- [x] 1.1 新增 `ToolSchemaAdapter`：实现 OpenAI/Anthropic 工具 schema 双向转换
- [x] 1.2 在 `agent_node` 中集成 `llm.bind_tools()`，移除 JSON Mode 依赖
- [x] 1.3 重新设计路由逻辑：基于 `AIMessage.tool_calls` 存在性判断 tool/chart_planner
- [x] 1.4 重写 `_REACT_SYSTEM_PROMPT`：移除 JSON 格式约束，改为 tool_calls 使用引导
- [x] 1.5 保留 JSON Mode fallback 路径（Provider 不支持 tool_calls 时自动降级）

## 2. Schema Version Management

- [x] 2.1 新增 `ToolSchemaVersion` 数据模型（version、parameters、deprecated_params、migration_note）
- [x] 2.2 新增 `VersionedTool` mixin/基类，支持多版本 schema 注册和查询
- [x] 2.3 实现兼容性校验：检查调用参数是否与目标 schema 版本兼容
- [x] 2.4 为 `TimeTool` 添加多版本 schema 示例（验证版本管理流程）
- [x] 2.5 写入版本化工具调用的事件追踪（记录 schema_version 到 tool_steps）

## 3. Streaming Tool Results

- [x] 3.1 在 `tool_node` 中注入 `StreamingEventBus`，支持发射 `tool.progress` 事件
- [x] 3.2 新增 `tool.output` 和 `tool.completed` SSE 事件类型到 `event_envelope.py`
- [x] 3.3 在 `event_mapper.py` 中新增 `tool.progress`/`tool.output`/`tool.completed` 映射
- [x] 3.4 为 `CodeSandboxTool` 添加流式输出能力（验证 streaming path）
- [x] 3.5 确保流式事件不影响 tool_steps 持久化和最终结果聚合

## 4. Parallel Execution — Per-tool Timeout

- [x] 4.1 在 `_execute_single_tool` 中激活 `BaseTool.timeout_ms` 超时控制（asyncio.wait_for）
- [x] 4.2 超时结果 SHALL 包含 `TOOL_TIMEOUT` 错误码且不影响其他并行工具结果
- [x] 4.3 确保 `_parallel_tool_execution` 的 asyncio.gather 在部分超时场景下正确合并

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
