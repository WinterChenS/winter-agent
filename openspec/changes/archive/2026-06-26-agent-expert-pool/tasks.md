# Tasks: agent-expert-pool

## Phase 1: DB + Model

- [x] **Task 1: Create agent_definitions table and SQLAlchemy model**
  创建 `agent_definitions` 表（PostgreSQL migration）和 Pydantic/SQLAlchemy 模型。Tests: CRUD 操作。

- [x] **Task 2: Create Agent CRUD API**
  `GET/POST/PUT/DELETE /api/v1/agents` 端点，Pydantic 校验。`POST /api/v1/agents/reload` 热刷新。Tests: 完整 CRUD 流。

## Phase 2: Agent Factory + Router

- [x] **Task 3: Create Agent Factory**
  运行时从 DB 读取 AgentDefinition，渲染 prompt 模板，绑定工具，构建 LLM。Tests: 不同 strategy 的 Agent 构建。

- [x] **Task 4: Create Router Agent**
  混合匹配：关键词优先 + LLM fallback。匹配结果含 agents 列表 + strategy。Tests: 关键词命中、LLM fallback、空结果。

## Phase 3: Collaboration Engine

- [x] **Task 5: Implement sequential collaboration**
  串行执行：Agent A → 结果注入 Agent B prompt → Agent B 执行。Tests: 两 Agent 串行链路。

- [x] **Task 6: Implement parallel collaboration**
  并行执行：多 Agent asyncio.gather → 汇总结果。Tests: 两 Agent 并行、错误隔离。

- [x] **Task 7: Implement supervisor collaboration**
  Supervisor Agent 拆解任务 → 分配给 workers → 汇总。Tests: 完整 supervisor 链路。

## Phase 4: Graph Integration

- [x] **Task 8: Rewrite graph.py for multi-agent topology**
  新图结构：RouterAgent → AgentFactory → Collaboration(串/并/Supervisor) → Merge → chart_planner → answer。Tests: 集成测试。

## Phase 5: Frontend Admin

- [x] **Task 9: Create Agent admin UI page**
  管理页面：Agent 列表（名称/工具/策略/开关）、创建/编辑表单（工具选择器、prompt 编辑器）、开关控制。路由 `/admin/agents`。

- [x] **Task 10: E2E integration test**
  完整流程：创建 Agent → 用户提问 → Router 匹配 → Agent 协作 → 流式输出。
