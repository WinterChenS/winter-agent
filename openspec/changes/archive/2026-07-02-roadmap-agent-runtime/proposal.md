## Why

Winter Agent 路线图包含 8 个阶段 40+ 个版本，但缺乏每个版本的具体技术实现 phase 规划。这导致后续开发缺少明确的技术方案、接口设计和验收标准。作为第一阶段，Agent Runtime（V0.1~V1.0）是整个平台的基石，需要优先产出详细的技术规划文档，其中 V0.1~V0.5 基于实际代码写回顾，V0.6~V1.0 基于路线图描述推演详细技术方案。

## What Changes

- 在 `docs/roadmap-phase-plans/` 下创建 10 个版本文档（V0.1~V1.0），每个文件包含该版本的详细技术 phase 规划
- V0.1~V0.5：基于代码库实际实现撰写回顾文档（实际技术方案、架构决策、关键代码路径）
- V0.6：Tool Runtime v2 规划（原生 tool_calls + 并行工具执行 + 流式结果 + Schema 版本管理），基于当前代码架构推演
- V0.7~V1.0：基于路线图描述 + 现有架构推演详细技术方案
- 每个文档统一模板：目标、技术方案、接口设计、数据结构、关键代码路径、Phase 拆分（含里程碑）、依赖关系、验收标准

## Capabilities

### New Capabilities

- `roadmap-agent-runtime-docs`: Agent Runtime 阶段（V0.1~V1.0）各版本技术 phase 规划文档

### Modified Capabilities

<!-- No existing specs modified -->

## Impact

- 新增目录 `docs/roadmap-phase-plans/` 存放版本规划文档
- 无代码变更，纯文档工作
- 后续 change（roadmap-workflow-engine 等）依赖此文档结构和模板
