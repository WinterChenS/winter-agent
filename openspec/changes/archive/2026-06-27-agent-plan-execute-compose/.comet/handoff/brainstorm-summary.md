# Brainstorm Summary

- Change: agent-plan-execute-compose
- Date: 2026-06-27

## 确认的技术方案

### Graph Topology
移除 router→collaboration→merge。新拓扑: entry(planning) → planning → execution (self-loop) → composer → END。fast path: planning 检测 trivial query 直接跳 composer。

### Planning Node
mini ReAct 循环（max 3 轮），只绑 search/browser/time 只读 Tool。JSON Mode LLM 输出结构化 Plan。JSON 验证失败重试 1 次，仍失败则降级为 minimal fallback plan。Trivial query (<20 chars / greeting) 直接出空 plan。

### Execution Node
严格按 plan.steps 顺序执行。每步先做 Artifact dedup check → 匹配则引用已有 artifact → 不匹配则执行 tool → 存储结果到 execution_results。Tool 失败重试 1 次，仍失败记录错误继续下一步。自循环递增 current_plan_step。

### Artifact Dedup
基于 (type, purpose_keywords) Jaccard 相似度 > 0.5 判别重复。中文分词 + 英文 lowercase 提取关键词。匹配记录到 reasoning_steps。

### Composer Node
Normal Mode LLM，上下文 = user query + plan + execution_results + artifacts(含上传 URL)。生成 Markdown 图文穿插报告，使用 ![title](url) 语法。不绑定任何 tool。

### SSE Integration
移除 collab_result 直发逻辑。composer 的 astream_events message.delta 直接流转发。plan 阶段 emit plan.started/completed 事件。

## 关键取舍与风险

- Planning 增加 1-3 轮 LLM 调用 → latency 增加，但 plan 质量提升
- 移除 RouterAgent/CollaborationEngine → 失去多 Agent 能力，用户确认接受
- Jaccard 去重可能误判 → 阈值 0.5 为 经验值，后续可调
- Execution 自循环依赖 LangGraph checkpoint → 需确保 checkpointer 正常工作

## 测试策略

- 手动测试: stock analysis query (完整三阶段), greeting query (fast path), duplicate chart (dedup)
- 单元测试: Jaccard dedup 算法, plan JSON validation
- 回归: SSE event format, message persistence, tool execution

## Spec Patch

无（OpenSpec delta spec 在 open 阶段已完整，无需回写）
