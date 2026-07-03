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

## 7. 风险与注意事项
```

### 2. 回顾文档 vs 规划文档

- **回顾文档（V0.1~V0.5）**：用 codegraph_explore 读取实际代码，描述"实际做了什么"而非"应该做什么"。标注关键 commit 和文件路径
- **规划文档（V0.6~V1.0）**：基于路线图描述 + 现有架构推演。标注"基于路线图推演，实际实现可能不同"

### 3. 文件组织

```
docs/roadmap-phase-plans/
├── V0.1-agent-runtime-basic-chat.md
├── V0.2-agent-runtime-multi-turn.md
├── V0.3-agent-runtime-tool-system.md
├── V0.4-agent-runtime-multi-agent.md
├── V0.5-agent-runtime-plan-execute.md
├── V0.6-agent-runtime-function-calling.md
├── V0.7-agent-runtime-context-builder.md
├── V0.8-agent-runtime-event-bus.md
├── V0.9-agent-runtime-stability.md
└── V1.0-agent-runtime-sdk.md
```

### 4. 信息获取策略

- **回顾文档**：使用 codegraph_explore 定位关键符号和代码路径，阅读实际源码
- **规划文档**：基于 README 路线图描述 + 开源社区最佳实践 + Winter Agent 现有架构约束

## Risks / Trade-offs

- [Risk] 规划文档可能与未来实际实现偏差较大 → 每个规划文档开头明确标注"基于路线图推演"，实际实现时需更新
- [Risk] codegraph 可能遗漏部分代码路径 → 结合 git log 和手动文件探索补充
- [Risk] 10 个文档工作量较大 → 按版本顺序逐个产出，每个 commit 一个版本
