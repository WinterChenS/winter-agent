---
comet_change: agent-backend-proxy
role: technical-design
canonical_spec: openspec
---

# Agent Backend Proxy — 技术设计文档

## 1. 架构总览

```
SpringBoot (JWT Auth)
   AgntController ──▶ AgentService ──▶ AgentClient (WebClient + X-User header)
                                              │
                                              ▼
                                    Python FastAPI
                                    /api/v1/agents/**
                                         │
                                         ▼
                                    AgentRepository
                                         │
                                         ▼
                                    PostgreSQL
                                    agent_definitions
```

三层职责：
- **AgentClient**: HTTP 通信封装，通过 ExchangeFilterFunction 统一注入 `X-User` header
- **AgentService**: 操作日志、异常转换（`WebClientRequestException` → 503）
- **AgentController**: REST 端点声明，`@Validated` 校验入参

## 2. PostgreSQL Migration

文件：`ai_service/db/migrations/V003__agent_upgrade.sql`

新增 9 列（全部 `ADD COLUMN IF NOT EXISTS` + DEFAULT）：

| 列名 | 类型 | 默认值 | 用途 |
|------|------|--------|------|
| `icon` | VARCHAR(64) | `''` | Emoji 或 icon 名称 |
| `agent_type` | VARCHAR(32) | `''` | Agent 分类 |
| `avatar_url` | TEXT | `''` | 头像 URL |
| `is_builtin` | BOOLEAN | `false` | 是否内置 |
| `tags` | JSONB | `'[]'` | 标签列表 |
| `metadata` | JSONB | `'{}'` | 扩展元数据 |
| `created_by` | VARCHAR | `''` | 创建者 |
| `updated_by` | VARCHAR | `''` | 最后修改者 |
| `version` | INTEGER | `1` | 乐观锁版本号 |

回填：5 个种子 agent 按 name 白名单设置 `is_builtin = true`。

## 3. Python: Model 扩展

`AgentDefinition` 新增字段（全部 Optional + 有默认值）：

```python
icon: str = ""
agent_type: str = ""
avatar_url: str = ""
is_builtin: bool = False
tags: list[str] = []
metadata: dict[str, Any] = {}
created_by: str = ""
updated_by: str = ""
version: int = 1
```

`model_params`（序列化别名 `model_config`）保持不变，包含 temperature/top_p/max_tokens/model_name 等。

## 4. Python: Repository 新增方法

### `set_enabled(agent_id: str, enabled: bool) → AgentDefinition | None`

```sql
UPDATE agent_definitions SET enabled=%s, updated_at=NOW() WHERE id=%s
RETURNING *
```

### `clone(agent_id: str, created_by: str = "") → AgentDefinition | None`

1. SELECT source agent by id
2. 生成新 `id`（`uuid4().hex[:12]`）
3. `name` 追加 `"-copy"`（冲突时追加数字后缀）
4. `display_name` 追加 `" (Copy)"`
5. `version=1`, `is_builtin=false`, `created_by=$created_by`, `created_at=NOW()`
6. INSERT 并 RETURNING

## 5. Python: API 端点

在 `api/routes/agents.py` 中新增 3 个端点：

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/v1/agents/{agent_id}/enable` | 启用 Agent |
| POST | `/api/v1/agents/{agent_id}/disable` | 禁用 Agent |
| POST | `/api/v1/agents/{agent_id}/clone` | 克隆 Agent |

三个端点从 `request.headers.get("X-User", "system")` 读取用户名。

现有 `create_agent`/`update_agent` 端点也读取 `X-User` 写入 `created_by`/`updated_by`。

## 6. SpringBoot: DTO

### AgentRequest（输入）
```java
public record AgentRequest(
    @NotBlank String name,
    @NotBlank String displayName,
    String description,
    String icon,
    String agentType,
    String avatarUrl,
    @NotBlank String systemPrompt,
    List<String> tools,
    Map<String, Object> modelConfig,
    List<String> triggerKeywords,
    String collaborationStrategy,
    Integer priority,
    Boolean enabled,
    List<String> tags,
    Map<String, Object> metadata
) {}
```

### AgentResponse（输出）
```java
public record AgentResponse(
    String id, String name, String displayName,
    String description, String icon, String agentType,
    String avatarUrl, String systemPrompt,
    List<String> tools, Map<String, Object> modelConfig,
    List<String> triggerKeywords, String collaborationStrategy,
    Integer priority, Boolean enabled, Boolean isBuiltin,
    List<String> tags, Map<String, Object> metadata,
    String createdBy, String updatedBy, Integer version,
    LocalDateTime createdAt, LocalDateTime updatedAt
) {}
```

## 7. SpringBoot: AgentClient

独立 `@Component`，使用专用 WebClient bean（`ExchangeFilterFunction` 统一注入 `X-User` header）：

```java
@Bean
public WebClient agentWebClient(
    @Value("${aichat.ai-service-url}") String baseUrl) {
    return WebClient.builder().baseUrl(baseUrl)
        .filter((req, next) -> {
            String username = ReactiveSecurityContextHolder.getContext()
                .map(ctx -> ctx.getAuthentication().getName())
                .defaultIfEmpty("system").block();
            return next.exchange(ClientRequest.from(req)
                .header("X-User", username).build());
        })
        .codecs(c -> c.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
        .build();
}
```

8 个方法：`listAll()`, `getById(id)`, `create(req)`, `update(id, req)`, `delete(id)`, `enable(id)`, `disable(id)`, `clone(id)`。每个方法返回 `Mono<T>`，JSON 反序列化为 DTO。

## 8. SpringBoot: AgentService & AgentController

### AgentService
- 每个方法：log 操作开始/完成
- 异常映射：`WebClientRequestException` / `ConnectException` → 503 "AI 服务不可用"
- 4xx/5xx 原样传播

### AgentController
- 8 个端点（见 tasks.md）
- `@Validated` 校验 AgentRequest
- 路径 `/api/agents/**` 已在 SecurityConfig 中受 JWT 保护，无需修改

## 9. 错误处理策略

| 场景 | HTTP 状态 | 消息 |
|------|-----------|------|
| Python 连接失败 | 503 | "AI 服务不可用，请稍后再试" |
| Agent 不存在 | 404 | 透传 Python 的 404 |
| 参数校验失败 | 400 | SpringBoot 自动返回 |
| Python 返回 5xx | 透传 | 原样转发 |

## 10. 兼容性保证

- Agent Runtime (`core/`, `graph/`) 完全不动
- SSE 流程 (`api/routes/chat.py`, `ChatController`) 完全不动
- 现有种子数据通过 `ADD COLUMN IF NOT EXISTS` + DEFAULT 值保护
- 新字段全部 Optional，现有 API 调用不受影响
