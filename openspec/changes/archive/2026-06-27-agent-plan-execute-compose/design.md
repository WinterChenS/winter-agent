## Context

当前生产图 `multi_agent_graph.py` 的拓扑为 `router → collaboration → merge → END`。`collaboration_node` 内部使用 LangChain 原生 function-calling，LLM 每轮思考即时决定调用什么 Tool（被动反应式），而不是先规划再执行。

遗留图 `graph.py` 有更接近目标的三阶段结构（ReAct → Chart Planner → Answer），但未在生产使用，且其 ReAct 循环同样是反应式的。

核心约束：禁止推翻当前架构、禁止新增复杂 Runtime、禁止多 Agent 协作。

## Goals / Non-Goals

**Goals:**
- 在 `multi_agent_graph.py` 上实现 Plan → Execute → Compose 三阶段
- Planning 生成结构化 JSON 执行计划（允许只读 Tool 辅助）
- Execution 按计划步骤依次执行，含 Artifact 去重
- Composer 生成图文穿插的专业 Markdown 报告
- 尽可能复用现有 `tool_node`、`answer_node` 等代码

**Non-Goals:**
- 不修改 `graph.py`（遗留图）
- 不重构 Tool 系统（`ToolRegistry`、`BaseTool` 保持不变）
- 不修改前端 SSE 协议
- 不新增外部依赖
- 不改造 `PolicyGate` 或 `checkpointer`

## Decisions

### Decision 1: 在 multi_agent_graph.py 内重构拓扑

**选择**：修改 `multi_agent_graph.py`，新增 3 个 node（planning/execution/composer），移除 router→collaboration→merge 流程。

**替代方案**：增强遗留图 `graph.py` 并切换到生产。否决理由：用户明确选择修改生产图，且 `multi_agent_graph.py` 的 `StreamingEventBus` 集成在 `chat.py` 中深度绑定。

**新拓扑**：
```
entry_point("planning")
planning ──(plan OK)──> execution
planning ──(plan failed after retry)──> execution  (降级：单步 plan)

execution ──(more steps)──> execution  (自循环)
execution ──(all done)──> composer

composer ──> END
```

### Decision 2: Planning Node 使用 JSON Mode LLM + 只读 Tool

**选择**：Planning 使用 JSON Mode LLM（`response_format: {"type": "json_object"}`），允许调用 search/browser 只读 Tool，禁止 chart/sandbox 等写入 Tool。Plan 格式错误时重试 1 次，仍失败则降级为单步直接执行。

**替代方案**：Planning 纯推理不调 Tool。否决理由：用户确认允许只读 Tool 辅助规划，提高计划准确性。

**JSON Plan Schema**：
```json
{
  "title": "报告标题",
  "steps": [
    {
      "step_id": 1,
      "description": "步骤描述",
      "required_data": ["需要的数据"],
      "required_tools": ["search"],
      "expected_artifacts": [
        {"type": "chart", "purpose": "图表用途", "chart_type": "line"}
      ]
    }
  ]
}
```

### Decision 3: Execution Node 自循环 + 步进计数

**选择**：Execution Node 使用 graph 条件边自循环，通过 `current_plan_step` 索引追踪进度。每轮执行一个 plan step，完成后 `current_plan_step++` 并循环回 execution，直到所有 step 完成。

**替代方案**：Execution Node 内部一次性 for 循环执行所有 step。否决理由：自循环方式可以利用 LangGraph checkpoint 在每步之间保存状态，便于断点恢复和前端进度展示。

### Decision 4: Artifact 去重采用关键词重叠匹配

**选择**：基于 `(type, purpose_keywords)` 的宽松匹配。预处理：对 purpose 文本做中文分词 + 英文 lowercase → 提取关键词集合 → 与已有 artifact 的 purpose 关键词集合计算 Jaccard 相似度 → 阈值 > 0.5 且 type 相同则判为重复。

**替代方案**：
- 严格 title 匹配：过于严格，漏掉实质重复
- 基于 step_id 匹配：无法处理跨步骤重复
- Embedding 语义匹配：增加外部依赖，过度设计

### Decision 5: Composer 复用 answer_node 的 Normal Mode LLM

**选择**：Composer 基于 `answer_node`（`nodes.py:746`）改造，输入为 SystemMessage(plan + results + artifacts context) + UserMessage(原始问题)，Normal Mode 生成 Markdown。

**替代方案**：JSON Mode Composer 输出结构化 blocks。否决理由：用户期望自然语言报告，Normal Mode Markdown 更自然。

### Decision 6: State 扩展最小化

**选择**：新增 5 个字段到 `State` TypedDict：

| 字段 | 类型 | 用途 |
|------|------|------|
| `execution_plan` | `dict \| None` | JSON 执行计划 |
| `execution_results` | `list[dict]` | 每步执行结果 `[{step_id, status, data, artifacts}]` |
| `artifacts` | `list[dict]` | 所有 artifact 元数据，用于去重 |
| `current_plan_step` | `int` | 当前执行步骤索引 |
| `plan_phase` | `str` | 当前阶段："planning"\|"executing"\|"composing"\|"done" |

## Risks / Trade-offs

- **[Risk] Planning LLM 生成不可执行的 plan** → Mitigation: JSON schema 验证 + 重试 + 降级为直接执行
- **[Risk] 增加 latency（多一次 Planning LLM 调用）** → Mitigation: Planning 使用非流式快速模型，仅 1 次调用
- **[Risk] 简单问题增加不必要的 overhead** → Mitigation: 短 query（<20 字符）或 greeting 类问题可跳过 planning，直接 execution + compose
- **[Risk] Execution 自循环可能死循环** → Mitigation: `current_plan_step` 检查 + max steps 上限 = len(plan.steps) + 2
- **[Trade-off] 移除 router 失去多 Agent 能力** → 用户明确选择，未来如需恢复可回退
