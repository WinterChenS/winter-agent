# Brainstorm Summary

- Change: agent-runtime-tool-v2
- Date: 2026-07-03

## 确认的技术方案

1. **并行执行（方案 A）**：同轮多 tool_calls 使用 asyncio.gather 并行执行，LLM 保证同轮调用互不依赖，依赖通过 ReAct 多轮迭代自然处理
2. **ReAct prompt 精简重写（方案 B）**：移除 JSON 格式约束，改用短 prompt 声明工具使用规则，guardrails 全部迁移到 agent_node 代码侧集中检查
3. **Guardrails 集中 agent_node 入口**：所有 guardrails（首轮禁止 final_answer、max_search、重复检测、max_iterations）在 agent_node 调用 LLM 前/后统一检查
4. **流式工具结果（方案 A）**：BaseTool 新增可选 `execute_stream` async generator，有则走流式路径，无则 tool_node 自动包装 emit tool.started/completed
5. **Schema 版本管理（方案 A）**：新增 VersionedTool mixin，schema_versions 存在工具上，不改 BaseTool
6. **Tool Metrics**：ToolRegistry 内内存 dict 存储，_execute_single_tool 记录，流结束通过 tool_summary SSE 推送
7. **Multi-Provider Adapter**：静态方法 to_openai/to_anthropic，bind_tools 时按 Provider 自动选择
8. **向后兼容**：Provider 不支持 tool_calls → JSON Mode fallback；旧工具无 execute_stream → 自动包装；旧工具无 schema_versions → BaseTool.schema 作为唯一版本

## 关键取舍与风险

- Provider 兼容性 → ToolSchemaAdapter 双向转换
- LLM 不遵循 tool_calls 协议 → _force_final_answer 兜底
- ReAct prompt 重写后行为变化 → 测试覆盖

## 测试策略

- 单元测试：ToolSchemaAdapter、VersionedTool、ToolMetrics、Guardrails
- 集成测试：bind_tools 路径 + JSON fallback 路径 + 流式工具事件路径
- 回归测试：全部现有测试套件

## Spec Patch

- 补充 delta spec 验收场景：bind_tools 不支持时的 fallback 行为、execute_stream 可选接口的向后兼容
