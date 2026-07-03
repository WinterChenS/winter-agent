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
