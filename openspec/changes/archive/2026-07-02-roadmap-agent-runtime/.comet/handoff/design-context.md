# Comet Design Handoff

- Change: roadmap-agent-runtime
- Phase: design
- Mode: compact
- Context hash: 92ac662bc50a58758c91cd37e062baf93257438cc78f3f2907a0e1228fd58ccf

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/roadmap-agent-runtime/proposal.md

- Source: openspec/changes/roadmap-agent-runtime/proposal.md
- Lines: 1-27
- SHA256: f46aba88b92c4018393103d2f8143a56b33d57aef46773c771c200e35d718e5a

```md
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
```

## openspec/changes/roadmap-agent-runtime/design.md

- Source: openspec/changes/roadmap-agent-runtime/design.md
- Lines: 1-114
- SHA256: 334483168519cc209aca73f8aa20f7d48402e453b7da4334c70d43248b3bbe35

[TRUNCATED]

```md
## Context

Winter Agent README 定义了 8 阶段路线图（约 40+ 个版本），当前已有的规划文档（如 `docs/enterprise-gap-analysis.md`）侧重高层差距分析，缺少每个版本的具体技术 phase 规划。本次 change 产出第一阶段 Agent Runtime（V0.1~V1.0）共 10 个版本的详细技术规划文档。

**当前状态**：
- V0.1~V0.5 已实现，代码存在于 `ai_service/` 中
- V0.6（原生 Function Calling Runtime）正在进行，chart-infrastructure-v2 等相关 change 活跃
- V0.7~V1.0 尚未开始

**代码库关键路径（通过 codegraph 探索获取）**：
- Tool 系统: `ai_service/tools/schema.py`, `ai_service/tools/registry.py`
- Agent 路由: `ai_service/core/router_agent.py`
- 图表模块: `ai_service/chart/chart_theme.py`, `ai_service/chart/chart_result.py`
- API 路由: `ai_service/api/routes/system.py`

## Goals / Non-Goals

**Goals:**
- 为 V0.1~V1.0 共 10 个版本产出一致格式的详细技术规划文档
- 已完成版本基于代码库实际实现写回顾（非虚构）
- 未完成版本基于现有架构推演技术方案，确保与现有代码衔接
- 每个文档包含：目标、技术方案、接口设计、数据结构、Phase 拆分、依赖、验收标准

**Non-Goals:**
- 不实现任何代码
- 不修改现有代码
- 不涉及 Workflow Engine（V1.1+）及之后的阶段
- 不创建 OpenSpec delta spec（纯文档 change）

## Decisions

### 1. 文档模板设计

每个版本规划文档采用统一结构：

```markdown
# VX.Y <版本名称>

## 1. 概述
- 目标：1-2 句核心目标
- 背景：为什么需要这个版本
- 状态：✅ 已完成 / 🚧 进行中 / 📋 规划中

## 2. 技术方案

### 2.1 架构概览
[ASCII 架构图]

### 2.2 核心组件
[组件职责和交互关系]

### 2.3 关键数据结构
[接口定义、数据模型]

### 2.4 关键代码路径
[核心流程的描述或伪代码]

## 3. Phase 拆分

| Phase | 名称 | 目标 | 关键交付物 | 预估工作量 |
|-------|------|------|-----------|-----------|
| Phase 1 | ... | ... | ... | ... |

## 4. 接口设计

### API 端点
| 方法 | 路径 | 请求 | 响应 | 说明 |

### 内部接口
[Python/Java 接口定义]

## 5. 依赖关系
- 前置版本：VX.Y
- 依赖模块：[列表]
- 外部依赖：[列表]

## 6. 验收标准
- [ ] AC1: ...
- [ ] AC2: ...

```

Full source: openspec/changes/roadmap-agent-runtime/design.md

## openspec/changes/roadmap-agent-runtime/tasks.md

- Source: openspec/changes/roadmap-agent-runtime/tasks.md
- Lines: 1-22
- SHA256: f1205804404b526ccec8b2297fb67eff2ac434bda93a2db6532cb235f4b13276

```md
## 1. 文档基础设施

- [ ] 1.1 创建 `docs/roadmap-phase-plans/` 目录

## 2. 已完成版本回顾（V0.1~V0.5）

- [ ] 2.1 V0.1 回顾：基础对话 + SSE 全链路流式响应
- [ ] 2.2 V0.2 回顾：多轮会话 + LangGraph Checkpoint + LangSmith 可观测性
- [ ] 2.3 V0.3 回顾：Tool Runtime（ReAct + Tool Registry + Strategy Guard）
- [ ] 2.4 V0.4 回顾：多 Agent 路由 + 顺序/并行/Supervisor 协作模式
- [ ] 2.5 V0.5 回顾：Plan-Execute-Synthesize 流水线 + ChartSpec 图表生成

## 3. 进行中版本规划（V0.6）

- [ ] 3.1 V0.6 规划：Tool Runtime v2（原生 tool_calls + 并行工具执行 + 流式结果 + Schema 版本管理）

## 4. 规划中版本推演（V0.7~V1.0）

- [ ] 4.1 V0.7 规划：Context Builder（会话/文件/Memory/Knowledge 上下文自动构建）
- [ ] 4.2 V0.8 规划：Event Bus（Tool/LLM/Workflow 全事件流）
- [ ] 4.3 V0.9 规划：Runtime Stability（Retry/Timeout/Cancellation/Checkpoint/Recovery）
- [ ] 4.4 V1.0 规划：Runtime SDK（统一 Agent Runtime API，所有 Agent 共用）
```

## openspec/changes/roadmap-agent-runtime/specs/roadmap-agent-runtime-docs/spec.md

- Source: openspec/changes/roadmap-agent-runtime/specs/roadmap-agent-runtime-docs/spec.md
- Lines: 1-38
- SHA256: 295b5eae1b88f227efea286c2d844c77fda3e282d5458a39a824114a485285a5

```md
# roadmap-agent-runtime-docs

Agent Runtime 阶段（V0.1~V1.0）各版本详细技术 phase 规划文档。

## Requirements

### Document Structure

每个版本文档必须包含以下章节：
1. **概述**：目标、背景、状态
2. **技术方案**：架构概览、核心组件、关键数据结构、关键代码路径
3. **Phase 拆分**：子阶段划分、每个 phase 的目标、交付物、预估工作量
4. **接口设计**：API 端点、内部接口定义
5. **依赖关系**：前置版本、依赖模块、外部依赖
6. **验收标准**：可验证的 checklist
7. **风险与注意事项**

### Documents

| 文件 | 版本 | 类型 |
|------|------|------|
| V0.1-agent-runtime-basic-chat.md | V0.1 | 回顾 |
| V0.2-agent-runtime-multi-turn.md | V0.2 | 回顾 |
| V0.3-agent-runtime-tool-system.md | V0.3 | 回顾 |
| V0.4-agent-runtime-multi-agent.md | V0.4 | 回顾 |
| V0.5-agent-runtime-plan-execute.md | V0.5 | 回顾 |
| V0.6-agent-runtime-function-calling.md | V0.6 | 规划 |
| V0.7-agent-runtime-context-builder.md | V0.7 | 规划 |
| V0.8-agent-runtime-event-bus.md | V0.8 | 规划 |
| V0.9-agent-runtime-stability.md | V0.9 | 规划 |
| V1.0-agent-runtime-sdk.md | V1.0 | 规划 |

### Quality Standards

- 回顾文档基于 codegraph 实际代码分析，标注关键文件路径
- 规划文档基于 README 路线图描述 + 现有架构约束推演
- 每个文档的 Phase 拆分为 3~5 个子阶段
- 接口设计使用代码块展示（TypeScript / Python / Java）
```

