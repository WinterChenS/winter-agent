---
comet_change: agent-runtime-tool-v2
role: technical-design
canonical_spec: openspec
---

# Agent Runtime Tool V2 — Technical Design

## Context

当前 Tool Runtime v1 通过 JSON Mode 引导 LLM 输出结构化 JSON 实现工具调用路由。`agent_node` 解析 `action` 字段决定进入 tool_node 或 chart_planner。存在 JSON 解析脆弱性和 Provider 锁定问题。V0.7 Context Builder 已就绪，本设计在此基础上替换工具调用机制。

## Architecture

```
                       ┌─────────────────────────────────────┐
                       │          agent_node                  │
                       │                                     │
                       │  1. bind_tools(tools) 调用 LLM      │
                       │  2. Guardrails 检查 (集中)           │
                       │  3. AIMessage.tool_calls?            │
                       │     ├─ 有 → route: tool              │
                       │     └─ 无 → route: chart_planner     │
                       └──────────┬──────────────────────────┘
                                  │
                   ┌──────────────┴──────────────┐
                   ▼                              ▼
          ┌─────────────┐               ┌──────────────────┐
          │  tool_node   │               │  chart_planner   │
          │              │               │  (不改动)        │
          │ parallel     │               └──────────────────┘
          │ execute      │
          │ + stream via │
          │ EventBus     │
          └──────┬───────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
┌──────┐  ┌──────────┐  ┌──────────┐
│Tool  │  │Versioned │  │ToolSchema│
│Metrics│ │Tool      │  │Adapter   │
│      │  │v1→v2→v3 │  │OAI⇄Anth  │
└──────┘  └──────────┘  └──────────┘
```

核心原则：agent_node 是唯一决策点，tool_node 是唯一执行点，StreamingEventBus 是唯一旁路通道。

## Decisions

### D1: 同轮多 tool_calls 并行执行

LLM 返回多个 tool_calls 时，tool_node 使用 asyncio.gather 并行执行。LLM 天然保证同轮调用互不依赖，有依赖的调用（如 search → browser）通过 ReAct 多轮迭代自然处理。复用现有 `_parallel_tool_execution` 逻辑。

### D2: ReAct prompt 精简重写 + Guardrails 代码化

JSON 格式约束由 `bind_tools` 机制保证，prompt 精简为短文本引导工具使用时机和 final_answer 条件。所有 guardrails 集中在 agent_node 入口：

| Guardrail | 触发逻辑 |
|-----------|---------|
| 首轮禁止 final_answer | 无 Observation 且 tool_calls 为空 → 强制注入 tool_calls |
| max_consecutive_search | 累计同轮 search 次数，超限 → _force_final_answer |
| 重复调用检测 | AIMessage 内容与上轮相似度 > 阈值 → _force_final_answer |
| max_iterations | iteration_count >= MAX_ITERATIONS → _force_final_answer |

### D3: BaseTool 新增可选 execute_stream

```python
class BaseTool(ABC):
    async def execute(self, input) -> ToolResult: ...
    
    async def execute_stream(self, input, bus: StreamingEventBus) -> ToolResult:
        """Optional: emit tool.progress / tool.output during execution."""
        return await self.execute(input)
```

- 基类提供默认实现（调用 execute，不 emit 中间事件）
- tool_node 统一处理：有 execute_stream → 传入 EventBus 走流式；无 → 自动 emit tool.started/completed 包装
- sandbox 等长执行工具重写 execute_stream 实现真正流式输出

### D4: VersionedTool mixin

```python
class VersionedTool(BaseTool):
    schema_versions: list[ToolSchemaVersion]
    
    def get_schema(self, version: str | None = None) -> ToolSchemaVersion:
        if version is None:
            return self.schema_versions[-1]
        return next(sv for sv in self.schema_versions if sv.version == version)
```

- BaseTool 不修改，需要版本管理的工具继承 VersionedTool
- ToolRegistry 按 name 索引，版本协商由工具自身处理
- Schema 版本使用 semver，deprecated_params 标记兼容性

### D5: Tool Metrics 内存存储

ToolRegistry 内 dict 存储，_execute_single_tool 记录每次调用的耗时和状态。提供 `get_metrics(name)` 查询接口。流结束通过 tool_summary SSE 事件推送前端。

### D6: ToolSchemaAdapter 静态方法

```python
class ToolSchemaAdapter:
    @staticmethod
    def to_openai(tool: BaseTool) -> dict: ...
    
    @staticmethod
    def to_anthropic(tool: BaseTool) -> dict: ...
```

bind_tools 时按当前 Provider 类型自动选择。不引入策略模式——两类 Provider 差异仅 schema 格式。

### D7: 向后兼容策略

| 场景 | 处理 |
|------|------|
| Provider 不支持 tool_calls | agent_node 检测配置 → fallback JSON Mode 路径 |
| 旧工具无 execute_stream | tool_node 调用 execute → 自动 emit started/completed 包装 |
| 旧工具无 schema_versions | BaseTool.schema 作为唯一版本，无需改动 |

## Risks

- **[Provider 兼容性]** 不同 Provider tool calling 格式差异 → ToolSchemaAdapter 双向转换
- **[LLM 行为漂移]** 精简 prompt 后 LLM 调用工具的时机可能变化 → 测试覆盖 + 保留 _force_final_answer
- **[流式事件顺序]** StreamingEventBus 异步推送 → merge_queue 保证事件顺序

## Testing Strategy

- **单元测试**：ToolSchemaAdapter、VersionedTool、ToolMetrics、Guardrails 纯函数
- **集成测试**：bind_tools 路径（模拟 LLM 返回 tool_calls）、JSON fallback 路径、流式事件完整链路
- **回归测试**：全部现有测试套件确认无破坏
