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
