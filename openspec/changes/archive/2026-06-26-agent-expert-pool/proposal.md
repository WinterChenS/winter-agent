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
