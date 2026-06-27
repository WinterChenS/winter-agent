# Brainstorm Summary

- Change: agent-expert-pool
- Date: 2026-06-25

## 确认的技术方案

1. **DB 存储方案**：PostgreSQL 单表 + JSONB（tools/keywords/model_config），每次请求查 DB 最新配置
2. **Router**：关键词匹配优先 + LLM fallback，匹配结果含 agents 列表 + strategy
3. **Agent Factory**：运行时查 DB → 渲染 prompt 模板 → 绑定 tools → 配置 LLM
4. **协作引擎**：sequential / parallel / supervisor 三种策略，结果汇总后流入现有三阶段流水线
5. **前端管理**：Agent 列表页 + 创建/编辑表单 + 开关控制

## 关键取舍与风险

- JSONB 灵活但无 DB 层校验 → 应用层 Pydantic 校验
- 每次查 DB 增加 ~5ms → Agent 执行 5-60s，可忽略
- 单 StateGraph 条件分支，不引入多图调度复杂度

## 测试策略

- DB CRUD 单元测试
- Router 关键词+LLM 测试
- Factory prompt 渲染测试
- 三种协作策略集成测试
- E2E：管理页 → 提问 → 组装 → 流式输出

## Spec Patch

无
