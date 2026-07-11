## Why

Event Bus 核心只有接入实际运行节点后才有价值。V0.8 需要让 LLM、Tool 和 Graph/Workflow 生命周期事件从源头发出，形成可观测、可订阅、可统一映射的 Agent Runtime 事件流。

## What Changes

- 在 LLM 调用边界发出 `llm.request`、`llm.response`、`llm.error` 事件；token 级事件按性能约束评估后接入或复用现有 `message.delta`。
- 在工具调用生命周期发出 `tool.invoke`、`tool.progress`、`tool.result`、`tool.error` 事件。
- 在 LangGraph 节点执行边界发出 `graph.enter`、`graph.exit`、`graph.error` 事件。
- 保持事件发布失败不影响主业务执行，错误记录为日志或降级事件。
- 不引入外部消息队列；全部事件源接入进程内 Event Bus。

## Capabilities

### New Capabilities

- `agent-runtime-event-sources`: LLM、Tool、Graph/Workflow 运行时事件源接入能力。

### Modified Capabilities

- 无。

## Impact

- 主要影响 `ai_service/graph/nodes.py`、`ai_service/tools`、`ai_service/core/runtime.py`、LLM 构造/调用边界和相关测试。
- 需要与现有工具执行、计划-执行-合成图、并行工具执行保持兼容。
- 为 SSE 适配和事件存储提供统一事件输入。
