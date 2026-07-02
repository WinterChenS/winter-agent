---
comet_change: roadmap-agent-runtime
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-02-roadmap-agent-runtime
status: final
---

# Agent Runtime Phase Planning — Design Doc

## Context

Winter Agent README 定义了 8 阶段路线图。当前缺少每个版本的具体技术实现 phase 规划，导致后续开发缺少明确的技术方案。本次产出第一阶段 Agent Runtime（V0.1~V1.0）共 10 个版本的详细技术规划文档。

**代码库状态**：V0.1~V0.5 已实现，V0.6 重定义为 Tool Runtime v2（原 Function Calling），V0.7~V1.0 规划中。

## Goals

- 产出 10 个版本文档到 `docs/roadmap-phase-plans/`
- V0.1~V0.5 基于 codegraph 实际代码写回顾
- V0.6~V1.0 基于路线图推演技术方案
- 每个文档 7 章节统一模板，5-7 个子 Phase

## Non-Goals

- 不实现代码
- 不修改现有代码
- 不涉及 Workflow Engine 及之后阶段

## Design Decisions

### 1. Document Template (7 sections)

```
1. 概述 — 目标、背景、状态(✅/🚧/📋)
2. 技术方案 — 架构图 + 核心组件 + 数据结构 + 关键代码路径
3. Phase 拆分 — 5-7 个子阶段表格
4. 接口设计 — API 端点 + Python/Java 内部接口
5. 依赖关系 — 前置版本 + 模块 + 外部依赖
6. 验收标准 — 可验证 checklist
7. 风险与注意事项
```

### 2. Research Method

**回顾文档**：codegraph_explore → 核心符号源码 → 关键代码路径 → 标注文件路径和 commit

**规划文档**：README 描述 → 现有架构约束 → 社区最佳实践 → 技术方案推演

### 3. Version Scope (V0.6 Redefined)

| 版本 | 名称 | 类型 |
|------|------|------|
| V0.1 | Basic Chat + SSE Streaming | 回顾 |
| V0.2 | Multi-turn + Checkpoint + Observability | 回顾 |
| V0.3 | Tool Runtime v1 (ReAct + Registry + Guard) | 回顾 |
| V0.4 | Multi-Agent Routing + Collaboration | 回顾 |
| V0.5 | Plan-Execute-Synthesize + ChartSpec | 回顾 |
| V0.6 | Tool Runtime v2 (native tool_calls + parallel + streaming + schema versioning) | 规划 |
| V0.7 | Context Builder (session/files/memory/knowledge) | 规划 |
| V0.8 | Event Bus (Tool/LLM/Workflow events) | 规划 |
| V0.9 | Runtime Stability (retry/timeout/cancellation/checkpoint/recovery) | 规划 |
| V1.0 | Runtime SDK (unified Agent Runtime API) | 规划 |

### 4. File Naming Convention

```
docs/roadmap-phase-plans/
├── V0.1-agent-runtime-basic-chat.md
├── V0.2-agent-runtime-multi-turn.md
├── V0.3-agent-runtime-tool-system.md
├── V0.4-agent-runtime-multi-agent.md
├── V0.5-agent-runtime-plan-execute.md
├── V0.6-agent-runtime-tool-v2.md
├── V0.7-agent-runtime-context-builder.md
├── V0.8-agent-runtime-event-bus.md
├── V0.9-agent-runtime-stability.md
└── V1.0-agent-runtime-sdk.md
```

### 5. Implementation Order

按版本号顺序逐个产出（V0.1 → V1.0），每个文档完成后 git commit。回顾文档优先产出以建立基线参考。

## Risks

| Risk | Mitigation |
|------|------------|
| 规划文档与未来实际实现偏差 | 文档开头标注"基于路线图推演，实际实现可能不同" |
| codegraph 可能遗漏部分代码 | 结合 git log 和手动文件探索补充 |
| V0.6 重定义范围扩大 | 明确 Tool Runtime v2 的核心交付物边界 |

## Open Questions

- V0.6 Tool Runtime v2 的具体 scope（并行执行 vs 流式结果优先级？）
- V0.7 Context Builder 的上下文优先级策略（session > files > memory?）
- V0.8 Event Bus 的技术选型（in-process pub/sub vs external MQ?）
