## Context

Workflow Engine 是 Winter Agent 从单 Agent 到多步骤 Workflow 的关键演进。第一阶段 Agent Runtime（V1.0）提供了统一 Runtime SDK，Workflow Engine 在此基础上构建 DAG 编排能力。所有版本均为规划类型（基于路线图推演），无回顾文档。

## Goals / Non-Goals

**Goals:**
- 为 V1.1~V1.5 共 5 个版本产出统一格式的技术规划文档
- 每个文档包含完整的 7 章节模板（概述/技术方案/Phase拆分/接口设计/依赖/验收/风险）
- 基于路线图描述推演技术方案，与 V1.0 Runtime SDK 衔接

**Non-Goals:**
- 不实现代码
- 不涉及 Knowledge Engine（V1.6+）及之后阶段

## Decisions

### 1. 文档模板

复用第一个 change 的 7 章节模板，格式保持一致。

### 2. 技术方案推演方法

- 基于 README 路线图描述 + 开源工作流引擎（Temporal/Airflow/Prefect）最佳实践
- 与 V1.0 Runtime SDK 接口衔接设计
- 每个文档 5-7 个子 Phase

### 3. 文件命名

```
docs/roadmap-phase-plans/
├── V1.1-workflow-engine-dag.md
├── V1.2-workflow-engine-control-flow.md
├── V1.3-workflow-engine-human-in-loop.md
├── V1.4-workflow-engine-checkpoint.md
└── V1.5-workflow-engine-designer.md
```

## Risks / Trade-offs

- 规划文档可能与未来实际实现偏差较大 → 文档开头标注"基于路线图推演"
- Workflow Designer（V1.5）涉及前端可视化，技术复杂度最高
