# Comet Design Handoff

- Change: roadmap-knowledge-engine
- Phase: design
- Mode: compact
- Context hash: 89cb52bb994b22bf788755af4abdd1d6c78b233ec2259d290bdc6a9a21b3edc2

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/roadmap-knowledge-engine/proposal.md

- Source: openspec/changes/roadmap-knowledge-engine/proposal.md
- Lines: 1-18
- SHA256: 3711eeb4780447ff49235aadfb75364f01084c3127babfaf4bb9e612b675802a

```md
## Why

Knowledge Engine（V1.6~V2.0）是 Winter Agent 从 Workflow 到知识驱动的关键演进。需要为 5 个版本产出详细技术规划文档。

## What Changes

- `docs/roadmap-phase-plans/` 下新增 5 个 Knowledge Engine 版本文档
- V1.6 文档解析、V1.7 OCR/多模态、V1.8 Hybrid Search、V1.9 ReRank/Citation/Cache、V2.0 Memory + 知识库

## Capabilities

### New Capabilities

- `roadmap-knowledge-engine-docs`: Knowledge Engine 阶段技术规划文档

## Impact

- 5 个 markdown 文件，纯文档工作
```

## openspec/changes/roadmap-knowledge-engine/design.md

- Source: openspec/changes/roadmap-knowledge-engine/design.md
- Lines: 1-22
- SHA256: 06d0c21c8a839477f7045db0588d5dbec4a83f714342e70c703b9e0d84052003

```md
## Context

Knowledge Engine 构建企业级知识引擎。复用 7 章节模板，基于路线图推演。

## Goals / Non-Goals

**Goals:** 5 个版本规划文档
**Non-Goals:** 不实现代码，不涉及 Skill Engine 之后

## Decisions

| 版本 | 文档名 | 焦点 |
|------|--------|------|
| V1.6 | Document Parsing | PDF/Word/Excel/PPT/Markdown |
| V1.7 | OCR + Multi-modal | OCR/图片理解/表格解析 |
| V1.8 | Hybrid Search | 全文+向量+Metadata |
| V1.9 | ReRank + Citation + Cache | 结果精排/引用/缓存 |
| V2.0 | Memory + Knowledge Base | 长期记忆+企业知识库+Workspace |

## Risks

- 规划文档与未来实现可能偏差
```

## openspec/changes/roadmap-knowledge-engine/tasks.md

- Source: openspec/changes/roadmap-knowledge-engine/tasks.md
- Lines: 1-5
- SHA256: ce4231e7040cb5941e868f846e1288c14bbe762ad3c35058b11cb5d2b46c5391

```md
- [ ] 1.1 V1.6 规划：文档上传、解析（PDF/Word/Excel/PPT/Markdown）
- [ ] 2.1 V1.7 规划：OCR、图片理解、表格解析、多模态知识抽取
- [ ] 3.1 V1.8 规划：Hybrid Search（全文+向量+Metadata）
- [ ] 4.1 V1.9 规划：ReRank、Citation、Knowledge Cache
- [ ] 5.1 V2.0 规划：长期 Memory + 企业知识库 + Workspace 隔离
```

## openspec/changes/roadmap-knowledge-engine/specs/roadmap-knowledge-engine-docs/spec.md

- Source: openspec/changes/roadmap-knowledge-engine/specs/roadmap-knowledge-engine-docs/spec.md
- Lines: 1-32
- SHA256: e9995e17ebf1541e6da8170eb2d3d81b7e6558dcb9630eddba99af98c6f43c3c

```md
# roadmap-knowledge-engine-docs

Knowledge Engine 阶段（V1.6~V2.0）技术规划文档。

## ADDED Requirements

### Requirement: Document Structure

每个版本文档 SHALL 包含 7 个章节。

#### Scenario: 用户查看文档
- **GIVEN** 打开 Knowledge Engine 阶段文档
- **WHEN** 浏览内容
- **THEN** 7 个章节完整且非空

### Requirement: Document Completeness

5 个文档 SHALL 全部存在且行数 > 100。

#### Scenario: 完整性检查
- **GIVEN** 5 个文档就绪
- **WHEN** 遍历列表
- **THEN** 每个文件存在且命名规范

### Requirement: Technical Accuracy

规划 SHALL 基于路线图描述推演，引用开源最佳实践。

#### Scenario: V1.8 Hybrid Search
- **GIVEN** 编写 V1.8 文档
- **WHEN** 描述技术方案
- **THEN** 包含全文搜索、向量搜索和元数据过滤的集成方案
```

