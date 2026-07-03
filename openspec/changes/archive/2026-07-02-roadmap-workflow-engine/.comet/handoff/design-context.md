# Comet Design Handoff

- Change: roadmap-workflow-engine
- Phase: design
- Mode: compact
- Context hash: 59c1bd8ae94f372b4b9f909eb83282c3e9b74ef32eeaa025bb04774eb0fd9a65

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/roadmap-workflow-engine/proposal.md

- Source: openspec/changes/roadmap-workflow-engine/proposal.md
- Lines: 1-29
- SHA256: 2510b8cc94827b7dbf638615df9c7364b242349ec5911f0d2952f20987b7e16d

```md
## Why

Winter Agent 第二阶段 Workflow Engine 路线图已定义（V1.1~V1.5），但缺乏每个版本的具体技术实现 phase 规划。Workflow Engine 是从 Agent 到 Workflow 的关键演进，需要为 DAG 引擎、流程控制、Human-in-the-loop、Checkpoint/Resume、可视化设计器 5 个版本产出详细技术规划文档。

## What Changes

- 在 `docs/roadmap-phase-plans/` 下创建 5 个 Workflow Engine 版本文档（V1.1~V1.5）
- V1.1：DAG Workflow Engine（节点+边模型、DAG 验证、拓扑排序执行）
- V1.2：流程控制（条件分支、循环、并行扇出、子流程、动态节点）
- V1.3：Human-in-the-loop（人工审批节点、确认节点、等待输入节点）
- V1.4：Checkpoint & Resume（流程快照、失败重试、补偿机制、断点恢复）
- V1.5：Workflow Designer（可视化拖拽 DAG 编辑器、节点配置面板）
- 每个文档采用 7 章节模板：概述→技术方案→Phase拆分→接口设计→依赖→验收标准→风险

## Capabilities

### New Capabilities

- `roadmap-workflow-engine-docs`: Workflow Engine 阶段（V1.1~V1.5）各版本技术 phase 规划文档

### Modified Capabilities

<!-- No existing specs modified -->

## Impact

- 新增 5 个文件到 `docs/roadmap-phase-plans/`
- 无代码变更，纯文档工作
- 与 Agent Runtime 文档共享目录和模板
```

## openspec/changes/roadmap-workflow-engine/design.md

- Source: openspec/changes/roadmap-workflow-engine/design.md
- Lines: 1-42
- SHA256: 26f94e81ca80d92ae1c471429b960a232634cb63f5843a3205f06acf0c842561

```md
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
```

## openspec/changes/roadmap-workflow-engine/tasks.md

- Source: openspec/changes/roadmap-workflow-engine/tasks.md
- Lines: 1-19
- SHA256: a812d2bf9710659b23a3008ecc8f828770d0e868959d89487e3aa6e32ee1f89a

```md
## 1. V1.1 DAG Workflow Engine

- [ ] 1.1 V1.1 规划：DAG Workflow Engine（节点+边、DAG 验证、拓扑排序执行）

## 2. V1.2 流程控制

- [ ] 2.1 V1.2 规划：条件分支、循环、并行扇出、子流程、动态节点

## 3. V1.3 Human-in-the-loop

- [ ] 3.1 V1.3 规划：人工审批、确认、等待输入节点

## 4. V1.4 Checkpoint & Resume

- [ ] 4.1 V1.4 规划：流程快照、失败重试、补偿机制、断点恢复

## 5. V1.5 Workflow Designer

- [ ] 5.1 V1.5 规划：可视化拖拽 DAG 编辑器、节点配置面板
```

## openspec/changes/roadmap-workflow-engine/specs/roadmap-workflow-engine-docs/spec.md

- Source: openspec/changes/roadmap-workflow-engine/specs/roadmap-workflow-engine-docs/spec.md
- Lines: 1-37
- SHA256: 55a8670984eb94bcfc90573825824caf65be0151ac7f3495b8131a07241452b7

```md
# roadmap-workflow-engine-docs

Workflow Engine 阶段（V1.1~V1.5）各版本详细技术 phase 规划文档。

## ADDED Requirements

### Requirement: Document Structure

每个版本文档 SHALL 包含 7 个章节：概述、技术方案、Phase 拆分、接口设计、依赖关系、验收标准、风险与注意事项。

#### Scenario: 用户查看任一文檔

- **GIVEN** 用户打开 Workflow Engine 阶段任一文檔
- **WHEN** 浏览文档内容
- **THEN** 文档包含全部 7 个章节且内容非空

### Requirement: Document Completeness

5 个版本文档 SHALL 全部存在且内容完整。

#### Scenario: 文档完整性检查

- **GIVEN** 5 个版本文档全部就绪
- **WHEN** 遍历文档列表
- **THEN** 每个文件存在且行数 > 100
- **AND** 文件名遵循 `VX.Y-workflow-engine-<feature>.md` 命名规范

### Requirement: Planning Document Quality

规划文档 SHALL 基于路线图描述推演技术方案，标注与前序版本的接口衔接。

#### Scenario: V1.1 文档与 V1.0 SDK 衔接

- **GIVEN** V1.0 Runtime SDK 提供了统一 Agent API
- **WHEN** 编写 V1.1 DAG Engine 文档
- **THEN** 接口设计章节引用 V1.0 SDK 接口
- **AND** 依赖关系标注 V1.0 为前置版本
```

