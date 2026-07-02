---
change: roadmap-agent-runtime
design-doc: docs/superpowers/specs/2026-07-02-roadmap-agent-runtime-design.md
base-ref: f65c67f88046cf58a4d632976967b31d8b32120d
---

# Implementation Plan: Agent Runtime Phase Planning

## Overview

为 Winter Agent 路线图 Agent Runtime 阶段（V0.1~V1.0）创建 10 个详细技术 phase 规划文档。
纯文档产出，不涉及代码实现。

## Execution Strategy

任务按版本号顺序执行（V0.1 → V1.0），每个文档完成后立即 commit。

### 文档产出流程（每个版本）

1. **codegraph 探索**（回顾文档）或 **技术推演**（规划文档）
2. **编写文档内容**：按 7 章节模板填充
3. **自检**：确认章节完整、无占位符
4. **git commit**：单文件提交

## Tasks

### Phase 1: 基础设施

- [x] 1.1 创建 `docs/roadmap-phase-plans/` 目录

### Phase 2: 回顾文档（V0.1~V0.5）

- [x] 2.1 V0.1 回顾：基础对话 + SSE 全链路流式响应
  - codegraph: SSE streaming chain (前端→BFF→AI Service)
  - 关键文件: ai_service/api/routes/, frontend/src/features/ai-chat/
- [x] 2.2 V0.2 回顾：多轮会话 + LangGraph Checkpoint + LangSmith 可观测性
  - codegraph: LangGraph graph nodes, checkpoint, LangSmith config
  - 关键文件: ai_service/graph/, ai_service/config.py
- [x] 2.3 V0.3 回顾：Tool Runtime v1（ReAct + Tool Registry + Strategy Guard）
  - codegraph: ToolRegistry, BaseTool, ReAct loop, guard
  - 关键文件: ai_service/tools/registry.py, ai_service/tools/schema.py
- [x] 2.4 V0.4 回顾：多 Agent 路由 + 顺序/并行/Supervisor 协作模式
  - codegraph: RouterAgent, collaboration strategies
  - 关键文件: ai_service/core/router_agent.py, ai_service/core/collaboration.py
- [x] 2.5 V0.5 回顾：Plan-Execute-Synthesize 流水线 + ChartSpec 图表生成
  - codegraph: planner, executor, synthesizer, ChartSpec, renderers
  - 关键文件: ai_service/graph/, ai_service/chart/

### Phase 3: 规划文档 V0.6

- [x] 3.1 V0.6 规划：Tool Runtime v2
  - 技术推演: native tool_calls, parallel execution, streaming results, schema versioning
  - 基于现有 ToolRegistry 架构扩展设计

### Phase 4: 规划文档（V0.7~V1.0）

- [x] 4.1 V0.7 规划：Context Builder
  - 技术推演: session/files/memory/knowledge context assembly
- [x] 4.2 V0.8 规划：Event Bus
  - 技术推演: Tool/LLM/Workflow event streaming
- [x] 4.3 V0.9 规划：Runtime Stability
  - 技术推演: retry/timeout/cancellation/checkpoint/recovery
- [x] 4.4 V1.0 规划：Runtime SDK
  - 技术推演: unified Agent Runtime API design
