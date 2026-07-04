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
