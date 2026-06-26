---
comet_change: agent-expert-pool
role: technical-design
canonical_spec: openspec
---

# Agent Expert Pool — Design Doc

## Architecture

```
User → RouterAgent → AgentFactory(DB) → CollaborationEngine → Merge → 三阶段流水线
                │            │                │
                ▼            ▼                ▼
          agent_definitions  ToolRegistry   sequential|parallel|supervisor
          (PostgreSQL)       (auto-discover)
```

## Component Design

### 1. DB Schema

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

### 2. Router Agent

```
1. 关键词匹配：遍历 enabled agents，计算 trigger_keywords 命中数
2. 命中 > 0 → 返回匹配的 agents + strategy（按 priority 排序，最多 3 个）
3. 命中 = 0 → LLM (轻量，temperature=0) 输出 {"agents":[...], "strategy":"..."}
4. 结果缓存 5 分钟（同 query hash）
```

### 3. Agent Factory

```python
class AgentFactory:
    def __init__(self, db_session, tool_registry):
        self.db = db_session
        self.tools = tool_registry

    async def build(self, definition: AgentDefinition, context: dict) -> AgentRuntime:
        prompt = definition.system_prompt.format(**context)
        tool_list = [self.tools.get(t) for t in definition.tools if self.tools.has(t)]
        llm = ChatOpenAI(
            model=settings.model,
            temperature=definition.model_config.get("temperature", 0.7),
            response_format={"type": "json_object"},
        )
        return AgentRuntime(name=definition.name, llm=llm, prompt=prompt, tools=tool_list)
```

### 4. Collaboration Engine

- **Sequential**: Agent[0].run() → result 注入 context → Agent[1].run() → ...
- **Parallel**: asyncio.gather([a.run() for a in agents]) → 汇总 merged result
- **Supervisor**: SupervisorAgent 拆解任务 → 分配 workers → asyncio.gather → 汇总

### 5. Graph Topology

```
START → router_node → factory_node → collaboration_node → merge → chart_planner → answer → END
```

### 6. Admin API

```
GET    /api/v1/agents          → list all agents
POST   /api/v1/agents          → create agent
GET    /api/v1/agents/{id}     → get agent detail
PUT    /api/v1/agents/{id}     → update agent
DELETE /api/v1/agents/{id}     → delete agent
POST   /api/v1/agents/reload   → clear cache, re-read DB
```

## Testing Strategy

1. DB model CRUD 单元测试（Pydantic 校验）
2. Router 关键词匹配 + LLM fallback 测试（mock DB）
3. Agent Factory prompt 渲染 + 工具绑定测试
4. sequential / parallel / supervisor 独立集成测试
5. Agent API CRUD 端点测试
6. E2E：管理页创建 Agent → 用户提问 → 动态组装 → 流式输出
