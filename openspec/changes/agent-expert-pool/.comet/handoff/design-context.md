# Comet Design Handoff

- Change: agent-expert-pool
- Phase: design
- Mode: compact
- Context hash: e04d7b9c665dddaf3f6fec5538f4441656c44b406da895772dfdc0fc1d5d7b59

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/agent-expert-pool/proposal.md

- Source: openspec/changes/agent-expert-pool/proposal.md
- Lines: 1-38
- SHA256: 6beef70558f5c35f5badbc377953fec8bd03a292967dd32e6d11282a6a6be4fc

```md
## Why

当前系统只有一个硬编码的 `agent.main`，所有能力耦合在单一 Agent 中。无法按场景切换 system prompt、工具集和模型配置，无法实现"数据分析师"、"研究员"、"写手"等多职责 Agent 协作。需要一个 DB 存储、运行时组装、前端可配置的动态 Agent 专家池系统。

## What Changes

- **Agent 定义存储**：PostgreSQL 新增 `agent_definitions` 表，存储每个 Agent 的 name/schema/prompt/tools/model/kwargs，支持 CRUD
- **Router Agent**：新增意图识别 + 专家匹配节点，混合关键词+LLM fallback 策略，从专家池选择最合适的 Agent 组合
- **Agent Factory**：运行时从 DB 读取配置，动态组装 system prompt + 工具集 + 模型参数
- **多 Agent 协作引擎**：支持 serial/parallel/supervisor 三种协作策略，Auto-parallel 引擎自动规划独立工具的并行执行
- **管理 API**：`/api/v1/agents` CRUD 端点，`/api/v1/agents/reload` 热刷新
- **管理前端**：Agent 列表页、创建/编辑表单、开关控制、工具选择器

## Capabilities

### New Capabilities

- `agent-definition-storage`: Agent 配置的 PostgreSQL 存储模型和 CRUD API
- `router-agent`: 意图识别 + 专家匹配，混合关键词规则和 LLM fallback
- `agent-factory`: 运行时动态组装 Agent（prompt 模板渲染 + 工具绑定 + 模型配置）
- `multi-agent-collaboration`: serial/parallel/supervisor 三种协作策略 + 结果汇总
- `agent-admin-ui`: 前端管理页面的 Agent 配置面板

### Modified Capabilities

<!-- 无已有 spec 需要修改 -->

## Impact

- **ai_service/models/**：新增 AgentDefinition SQLAlchemy 模型
- **ai_service/db/**：新增数据库迁移脚本
- **ai_service/core/agent_factory.py**：新建 Agent Factory
- **ai_service/graph/router_node.py**：新建 Router Agent 节点
- **ai_service/graph/collaboration.py**：新建协作引擎
- **ai_service/graph/graph.py**：重构图为 Router → Agents → Merge 拓扑
- **ai_service/api/routes/agents.py**：新建 Agent CRUD API
- **frontend/src/pages/AdminPanel.tsx**：新建管理页面
- **frontend/src/components/AgentEditor.tsx**：新建 Agent 编辑表单
```

## openspec/changes/agent-expert-pool/design.md

- Source: openspec/changes/agent-expert-pool/design.md
- Lines: 1-76
- SHA256: 3c596f8aee739e47b5f63c6a86e1fb9e551070f08f308c3055d9f019e766c879

```md
## Context

当前 `graph/graph.py` 构建单一 `StateGraph`，`agent.main` 硬编码。需改造为 Router → Agent Factory → 动态 Agent Graph → Merge 拓扑。

## Goals / Non-Goals

**Goals:**
- Agent 配置全部存 DB，运行时可热更新（每次请求查最新配置）
- Router 混合匹配（关键词规则 + LLM fallback）
- 三种协作策略：sequential、parallel、supervisor
- 管理 API + 前端管理页面

**Non-Goals:**
- 不做 Agent 间自主通信（图内调度）
- 不做知识库/RAG 集成
- 不做多轮 Agent 切换

## Decisions

### 1. DB Schema：单表 + JSONB

```sql
CREATE TABLE agent_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(64) UNIQUE NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL,
    tools JSONB NOT NULL DEFAULT '[]',
    model_config JSONB NOT NULL DEFAULT '{"temperature":0.7}',
    trigger_keywords JSONB NOT NULL DEFAULT '[]',
    collaboration_strategy VARCHAR(16) NOT NULL DEFAULT 'sequential',
    priority INT NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**选择理由**：JSONB 灵活存储 tools/trigger_keywords/model_config，无需关联表。单 Agent 的工具数量少（<20），JSONB 完全够用。

### 2. Router：关键词优先 + LLM fallback

```
1. 关键词匹配：遍历 enabled agents，计算 trigger_keywords 命中数
2. 命中 >0 → 直接返回匹配的 agents + strategy
3. 命中 =0 → 调用 LLM (轻量模型) 输出 {"agents":[...], "strategy":"..."}
4. 匹配结果缓存 5 分钟（同 query hash）
```

### 3. Agent Factory

```python
class AgentFactory:
    async def build_agent(self, definition: AgentDefinition) -> Runnable:
        prompt = self._render_prompt(definition.system_prompt, context)
        tools = self._resolve_tools(definition.tools)
        llm = self._build_llm(definition.model_config)
        return llm.bind_tools(tools) if tools else llm
```

### 4. 协作策略

- **Sequential**：Agent A 执行 → 结果注入 Agent B prompt → Agent B 执行
- **Parallel**：多个 Agent 同时执行 → 汇总结果
- **Supervisor**：Supervisor Agent 拆解任务 → 分配给 workers → 汇总

### 5. 前端管理页

路由 `GET /admin/agents`：Vite + React，列表页 + 表单弹窗。工具选择器用 checkbox 展示可用工具列表。

## Risks / Trade-offs

- [风险] 每次请求查 DB 增加延迟 → 单条查询 ~5ms，Agent 执行时间 5-60s，可忽略
- [风险] JSONB 存储无 schema 校验 → 应用层 Pydantic 校验 + 保存前验证
- [取舍] 放弃图内多 Agent 通信 → 用 prompt 注入上下文替代，简化实现
```

## openspec/changes/agent-expert-pool/tasks.md

- Source: openspec/changes/agent-expert-pool/tasks.md
- Lines: 1-41
- SHA256: 4a856359c974f85e81a53ebffc7bfe710373875ca7aa835a7731c121b169bbbf

```md
# Tasks: agent-expert-pool

## Phase 1: DB + Model

- [ ] **Task 1: Create agent_definitions table and SQLAlchemy model**
  创建 `agent_definitions` 表（PostgreSQL migration）和 Pydantic/SQLAlchemy 模型。Tests: CRUD 操作。

- [ ] **Task 2: Create Agent CRUD API**
  `GET/POST/PUT/DELETE /api/v1/agents` 端点，Pydantic 校验。`POST /api/v1/agents/reload` 热刷新。Tests: 完整 CRUD 流。

## Phase 2: Agent Factory + Router

- [ ] **Task 3: Create Agent Factory**
  运行时从 DB 读取 AgentDefinition，渲染 prompt 模板，绑定工具，构建 LLM。Tests: 不同 strategy 的 Agent 构建。

- [ ] **Task 4: Create Router Agent**
  混合匹配：关键词优先 + LLM fallback。匹配结果含 agents 列表 + strategy。Tests: 关键词命中、LLM fallback、空结果。

## Phase 3: Collaboration Engine

- [ ] **Task 5: Implement sequential collaboration**
  串行执行：Agent A → 结果注入 Agent B prompt → Agent B 执行。Tests: 两 Agent 串行链路。

- [ ] **Task 6: Implement parallel collaboration**
  并行执行：多 Agent asyncio.gather → 汇总结果。Tests: 两 Agent 并行、错误隔离。

- [ ] **Task 7: Implement supervisor collaboration**
  Supervisor Agent 拆解任务 → 分配给 workers → 汇总。Tests: 完整 supervisor 链路。

## Phase 4: Graph Integration

- [ ] **Task 8: Rewrite graph.py for multi-agent topology**
  新图结构：RouterAgent → AgentFactory → Collaboration(串/并/Supervisor) → Merge → chart_planner → answer。Tests: 集成测试。

## Phase 5: Frontend Admin

- [ ] **Task 9: Create Agent admin UI page**
  管理页面：Agent 列表（名称/工具/策略/开关）、创建/编辑表单（工具选择器、prompt 编辑器）、开关控制。路由 `/admin/agents`。

- [ ] **Task 10: E2E integration test**
  完整流程：创建 Agent → 用户提问 → Router 匹配 → Agent 协作 → 流式输出。
```

