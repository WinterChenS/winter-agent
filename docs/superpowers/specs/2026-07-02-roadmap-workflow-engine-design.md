---
comet_change: roadmap-workflow-engine
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-02-roadmap-workflow-engine
status: final
---

# Workflow Engine Phase Planning — Design Doc

## Context

Workflow Engine（V1.1~V1.5）从 Agent 演进为 Workflow，实现复杂任务编排。在 V1.0 Runtime SDK 基础上构建 DAG 引擎。

## Goals

- 产出 5 个版本规划文档到 `docs/roadmap-phase-plans/`
- 复用 7 章节模板
- 基于路线图推演技术方案

## Non-Goals

- 不实现代码、不涉及 Knowledge Engine 及之后阶段

## Design Decisions

| 版本 | 文档名 | 核心设计焦点 |
|------|--------|------------|
| V1.1 | DAG Workflow Engine | 节点+边模型、DAG 验证、拓扑排序执行 |
| V1.2 | 流程控制 | 条件/循环/并行/子流程/动态节点 |
| V1.3 | Human-in-the-loop | 审批/确认/等待输入节点 |
| V1.4 | Checkpoint & Resume | 快照/重试/补偿/断点恢复 |
| V1.5 | Workflow Designer | 可视化拖拽编辑器 |

## Risks

- 规划文档与未来实现可能偏差 → 文档标注"基于路线图推演"
