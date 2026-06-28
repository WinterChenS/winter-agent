# Brainstorm Summary

- Change: agent-backend-proxy
- Date: 2026-06-28

## 确认的技术方案

**PostgreSQL**: V003 migration 用 `ALTER TABLE ADD COLUMN IF NOT EXISTS` 新增 9 个扩展字段（icon/agent_type/avatar_url/is_builtin/tags/metadata/created_by/updated_by/version），全部有 DEFAULT 值，幂等安全。按 name 白名单回填 5 个种子 agent 的 is_builtin=true。model 参数保留在 model_config JSONB 中。

**Python FastAPI**: AgentDefinition Pydantic model 新增 9 个 Optional 字段（全部带默认值）。AgentRepository 新增 set_enabled() 和 clone() 方法。新增 3 个端点（enable/disable/clone），从 X-User request header 读取用户名。现有 CRUD 端点也读取 X-User 写入 created_by/updated_by。Agent Runtime/Graph/SSE 完全不动。

**SpringBoot**: 三层架构 Controller→Service→Client。AgentClient 用 ExchangeFilterFunction 统一添加 X-User header（从 SecurityContext 提取当前用户名）。AgentService 处理日志和异常转换（WebClientRequestException→503）。AgentController 提供 8 个 REST 端点。SecurityConfig 无需修改（/api/agents/** 已受保护）。

## 关键取舍与风险

- **[取舍] model_name/temperature/top_p/max_tokens 保留在 model_config JSONB**，不独立建列，避免数据冗余和双写同步问题
- **[风险] Migration 回滚** → 新增列均可空/有默认值，可安全回滚（DROP COLUMN）
- **[风险] clone 名称冲突** → name 追加 "-copy" 后缀，若仍冲突则追加数字后缀

## 测试策略

- 单元测试：Python AgentRepository set_enabled/clone 方法
- 集成测试：Python enable/disable/clone 端点（使用 Mock repo）
- 手动验证：SpringBoot 代理端点返回正确数据
- 回归测试：发送聊天消息确保 SSE 流程未受影响

## Spec Patch

无
