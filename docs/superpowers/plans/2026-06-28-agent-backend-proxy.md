---
change: agent-backend-proxy
design-doc: docs/superpowers/specs/2026-06-28-agent-backend-proxy-design.md
base-ref: a343245c2db0ada74e19f575f1bbfe6b2cd70446
---

# Agent Backend Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 SpringBoot 后端和 Python FastAPI 服务之间构建完整的 Agent CRUD 代理层，新增 enable/disable/clone 端点，扩展 AgentDefinition 模型以支持额外元数据字段。

**Architecture:** 三层代理架构：SpringBoot Controller 暴露 REST 端点，Service 层处理业务逻辑和异常转换，AgentClient（WebClient + X-User header 注入）将请求转发至 Python FastAPI。Python 侧新增模型字段、仓库方法（set_enabled、clone）和 API 端点。

**Tech Stack:** Python 3.12 + FastAPI + Pydantic + psycopg_pool, SpringBoot 3.4.5 + WebFlux + WebClient + ReactiveSecurityContextHolder, PostgreSQL 16

## Global Constraints

- 所有 SQL 变更必须使用 `ADD COLUMN IF NOT EXISTS` + DEFAULT 值，确保向后兼容
- 新字段全部 Optional/Python 默认值，现有 API 调用不受影响
- Agent Runtime (`core/`, `graph/`) 完全不动
- SSE 流程 (`api/routes/chat.py`, `ChatController`) 完全不动
- Java 使用 record 模式定义 DTO，不可使用 Lombok
- 所有 Python 异步测试标记 `@pytest.mark.asyncio`
- SpringBoot 测试使用 JUnit 5 + Mockito + reactor-test StepVerifier
- 每次 commit 前必须运行所有相关测试
- 使用 TDD 循环：写测试 → 运行验证失败 → 实现 → 运行验证通过 → commit

---

## 文件结构总览

### 新建文件

| 文件 | 职责 |
|------|------|
| `ai_service/db/migrations/V003__agent_upgrade.sql` | 9 列新增 + 种子 agent 回填 |
| `backend/src/main/java/com/example/aichat/dto/AgentRequest.java` | 输入 DTO，携带 `@NotBlank` 等校验注解 |
| `backend/src/main/java/com/example/aichat/dto/AgentResponse.java` | 输出 DTO，映射所有 Agent 字段 |
| `backend/src/main/java/com/example/aichat/client/AgentClient.java` | 封装 WebClient HTTP 通信，8 个方法 |
| `backend/src/main/java/com/example/aichat/service/AgentService.java` | 业务逻辑层，日志 + 异常转换 |
| `backend/src/test/java/com/example/aichat/dto/AgentRequestTest.java` | AgentRequest 校验测试 |
| `backend/src/test/java/com/example/aichat/dto/AgentResponseTest.java` | AgentResponse 序列化测试 |
| `backend/src/test/java/com/example/aichat/client/AgentClientTest.java` | AgentClient 方法测试 |
| `backend/src/test/java/com/example/aichat/service/AgentServiceTest.java` | AgentService 逻辑 + 异常测试 |
| `backend/src/test/java/com/example/aichat/controller/AgentControllerTest.java` | AgentController 端点测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `ai_service/models/agent.py` | AgentDefinition 新增 9 个字段 |
| `ai_service/repositories/agent_repository.py` | 新增 set_enabled/clone 方法，更新 SQL/helper |
| `ai_service/api/routes/agents.py` | 新增 3 个端点，更新现有端点读取 X-User |
| `ai_service/tests/test_agent_model.py` | 新增字段测试 |
| `ai_service/tests/test_agent_api.py` | 新增 set_enabled/clone/X-User 测试 |
| `backend/src/main/java/com/example/aichat/config/WebFluxConfig.java` | 新增 agentWebClient bean（X-User filter） |
| `backend/src/main/java/com/example/aichat/controller/AgentController.java` | 完整重写为 8 个端点 |
| `backend/pom.xml` | 新增 `spring-boot-starter-validation` 依赖 |

---

### Task 1: DB Migration — 创建 V003 迁移文件

**Files:**
- Create: `ai_service/db/migrations/V003__agent_upgrade.sql`

**Interfaces:**
- Consumes: 现有表 `agent_definitions`（定义见 `001_create_agent_definitions.sql`）
- Produces: 迁移 SQL，包含 9 个 `ADD COLUMN IF NOT EXISTS` + 白名单回填 `UPDATE`

- [x] **Step 1: 创建迁移文件，写入 9 列新增 SQL**

```sql
-- ================================================================
-- Migration V003: Agent table upgrade — new fields extension
-- Run: psql $DATABASE_URL -f ai_service/db/migrations/V003__agent_upgrade.sql
-- ================================================================

BEGIN;

ALTER TABLE agent_definitions
    ADD COLUMN IF NOT EXISTS icon VARCHAR(64) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS agent_type VARCHAR(32) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS avatar_url TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS is_builtin BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS created_by VARCHAR NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS updated_by VARCHAR NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

COMMIT;
```

- [x] **Step 2: 在同一个文件末尾添加种子 Agent 回填**

在 COMMIT 之前，在 BEGIN...COMMIT 块内追加：

```sql
-- Backfill: mark known seed agents as built-in
UPDATE agent_definitions SET is_builtin = true
WHERE name IN ('search', 'code_analyst', 'web_researcher', 'general', 'data_analyst');
```

最终文件的 BEGIN/COMMIT 块包含两部分：ALTER TABLE（9 列）和 UPDATE（5 行回填）。

- [x] **Step 3: 验证迁移 SQL**

运行: `psql postgresql://localhost:5432/ai_chat -f ai_service/db/migrations/V003__agent_upgrade.sql`
预期输出: `ALTER TABLE` 成功，`UPDATE 5`。

验证: `psql postgresql://localhost:5432/ai_chat -c "\d agent_definitions"` 显示 9 个新列。
验证: `psql postgresql://localhost:5432/ai_chat -c "SELECT name, is_builtin FROM agent_definitions WHERE is_builtin = true;"` 返回 5 行。

- [x] **Step 4: Commit**

```bash
git add ai_service/db/migrations/V003__agent_upgrade.sql
git commit -m "feat(db): add V003 migration with 9 new agent columns and is_builtin backfill"
```

---

### Task 2: Python Model — 扩展 AgentDefinition

**Files:**
- Modify: `ai_service/models/agent.py`
- Test: `ai_service/tests/test_agent_model.py`

**Interfaces:**
- Consumes: `AgentDefinition` 现有模型
- Produces: `AgentDefinition` 新增 9 个可选字段

- [x] **Step 1: 写新字段的测试**

在 `ai_service/tests/test_agent_model.py` 末尾追加：

```python
def test_agent_definition_new_fields_defaults():
    agent = AgentDefinition(
        name="new_fields",
        display_name="New Fields",
        system_prompt="Test.",
    )
    assert agent.icon == ""
    assert agent.agent_type == ""
    assert agent.avatar_url == ""
    assert agent.is_builtin is False
    assert agent.tags == []
    assert agent.metadata == {}
    assert agent.created_by == ""
    assert agent.updated_by == ""
    assert agent.version == 1


def test_agent_definition_new_fields_custom():
    agent = AgentDefinition(
        name="custom",
        display_name="Custom",
        system_prompt="Test.",
        icon="🤖",
        agent_type="assistant",
        avatar_url="https://example.com/avatar.png",
        is_builtin=True,
        tags=["ai", "chat"],
        metadata={"tier": "premium"},
        created_by="admin",
        updated_by="admin",
        version=3,
    )
    assert agent.icon == "🤖"
    assert agent.agent_type == "assistant"
    assert agent.tags == ["ai", "chat"]
    assert agent.metadata == {"tier": "premium"}
    assert agent.version == 3
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_model.py::test_agent_definition_new_fields_defaults tests/test_agent_model.py::test_agent_definition_new_fields_custom -v`
预期输出: 两个测试均 FAIL，错误类型为 `pydantic.ValidationError` 或字段不存在。

- [x] **Step 3: 在 AgentDefinition 中新增字段**

在 `ai_service/models/agent.py` 的 `AgentDefinition` 类中的 `enabled: bool = True` 之后追加：

```python
    icon: str = ""
    agent_type: str = ""
    avatar_url: str = ""
    is_builtin: bool = False
    tags: list[str] = []
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str = ""
    updated_by: str = ""
    version: int = 1
```

注意：`metadata` 使用 `Field(default_factory=dict)` 而非 `{}`，避免可变默认值陷阱。

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_model.py -v`
预期输出: 全部测试 PASS（原有 4 个 + 新增 2 个，共 6 个）。

- [x] **Step 5: Commit**

```bash
git add ai_service/models/agent.py ai_service/tests/test_agent_model.py
git commit -m "feat(python): extend AgentDefinition model with 9 new optional fields"
```

---

### Task 3: Python Repo — 更新 SQL 常量和 helper

**Files:**
- Modify: `ai_service/repositories/agent_repository.py`

**Interfaces:**
- Consumes: `AgentDefinition` 新字段
- Produces: 更新的 `_AGENT_SELECT`、`_AGENT_COLS`、`_row_to_agent()`，包含 9 个新列

- [ ] **Step 1: 更新 _AGENT_SELECT 和 _AGENT_COLS**

将 `_AGENT_SELECT` SQL 扩展为包含新列：

```python
_AGENT_SELECT = """
    SELECT id, name, display_name, description, system_prompt,
           tools, model_config, trigger_keywords, collaboration_strategy,
           priority, enabled, icon, agent_type, avatar_url, is_builtin,
           tags, metadata, created_by, updated_by, version
    FROM agent_definitions
"""
```

将 `_AGENT_COLS` 更新：

```python
_AGENT_COLS = ["id", "name", "display_name", "description", "system_prompt",
               "tools", "model_config", "trigger_keywords", "collaboration_strategy",
               "priority", "enabled", "icon", "agent_type", "avatar_url", "is_builtin",
               "tags", "metadata", "created_by", "updated_by", "version"]
```

- [ ] **Step 2: 更新 _row_to_agent，增加 tags 和 metadata 的 JSON 反序列化**

将 JSON 字段列表从 3 个扩展为 5 个：

```python
def _row_to_agent(row: Any) -> AgentDefinition:
    """Convert a database row to an AgentDefinition."""
    d = dict(zip(_AGENT_COLS, row))
    for field in ("tools", "model_config", "trigger_keywords", "tags", "metadata"):
        if isinstance(d.get(field), str):
            d[field] = _json.loads(d[field])
    return AgentDefinition(**d)
```

- [ ] **Step 3: 运行现有测试确认向后兼容**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py tests/test_agent_model.py -v`
预期输出: 所有测试 PASS。

- [ ] **Step 4: Commit**

```bash
git add ai_service/repositories/agent_repository.py
git commit -m "feat(python): update _AGENT_SELECT, _AGENT_COLS, _row_to_agent for new fields"
```

---

### Task 4: Python Repo — 更新 create/update 方法

**Files:**
- Modify: `ai_service/repositories/agent_repository.py`
- Test: `ai_service/tests/test_agent_api.py`

**Interfaces:**
- Consumes: `AgentDefinition` 9 个新字段
- Produces: `PostgresAgentRepository.create()` 和 `update()` 支持全部 20 个字段

- [ ] **Step 1: 写新字段持久化测试**

在 `ai_service/tests/test_agent_api.py` 末尾追加（使用 MockAgentRepository）：

```python
@pytest.mark.asyncio
async def test_create_with_new_fields(repo: AgentRepository) -> None:
    agent = AgentDefinition(
        name="full", display_name="Full", system_prompt="...",
        icon="🤖", agent_type="assistant", tags=["ai"],
        metadata={"key": "val"}, created_by="admin",
        version=2,
    )
    created = await repo.create(agent)
    assert created.icon == "🤖"
    assert created.tags == ["ai"]
    assert created.metadata == {"key": "val"}
    assert created.version == 2


@pytest.mark.asyncio
async def test_update_preserves_new_fields(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    created.icon = "🆕"
    created.tags = ["updated"]
    result = await repo.update(created.id, created)
    assert result is not None
    assert result.icon == "🆕"
    assert result.tags == ["updated"]
```

- [ ] **Step 2: 运行测试确认 Mock 版本通过**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_create_with_new_fields tests/test_agent_api.py::test_update_preserves_new_fields -v`
预期输出: 两个测试 PASS（Mock 版本已支持新字段，因为 AgentDefinition 自动携带）。

- [ ] **Step 3: 更新 PostgresAgentRepository 的 INSERT 和 UPDATE SQL**

更新 `create()` 方法中的 INSERT SQL：

```python
async def create(self, agent: AgentDefinition) -> AgentDefinition:
    async with self._pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO agent_definitions (id, name, display_name, description,
                system_prompt, tools, model_config, trigger_keywords,
                collaboration_strategy, priority, enabled,
                icon, agent_type, avatar_url, is_builtin,
                tags, metadata, created_by, updated_by, version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                agent.id, agent.name, agent.display_name, agent.description,
                agent.system_prompt,
                _json.dumps(agent.tools), _json.dumps(agent.model_params),
                _json.dumps(agent.trigger_keywords), agent.collaboration_strategy,
                agent.priority, agent.enabled,
                agent.icon, agent.agent_type, agent.avatar_url, agent.is_builtin,
                _json.dumps(agent.tags), _json.dumps(agent.metadata),
                agent.created_by, agent.updated_by, agent.version,
            ),
        )
    return agent
```

更新 `update()` 方法中的 UPDATE SQL：

```python
await conn.execute(
    """
    UPDATE agent_definitions SET
        name = %s, display_name = %s, description = %s,
        system_prompt = %s, tools = %s, model_config = %s,
        trigger_keywords = %s, collaboration_strategy = %s,
        priority = %s, enabled = %s,
        icon = %s, agent_type = %s, avatar_url = %s, is_builtin = %s,
        tags = %s, metadata = %s, created_by = %s, updated_by = %s, version = %s
    WHERE id = %s
    """,
    (
        agent.name, agent.display_name, agent.description,
        agent.system_prompt,
        _json.dumps(agent.tools), _json.dumps(agent.model_params),
        _json.dumps(agent.trigger_keywords), agent.collaboration_strategy,
        agent.priority, agent.enabled,
        agent.icon, agent.agent_type, agent.avatar_url, agent.is_builtin,
        _json.dumps(agent.tags), _json.dumps(agent.metadata),
        agent.created_by, agent.updated_by, agent.version,
        agent_id,
    ),
)
```

注意：`update()` 中的 `version` 字段赋值直接使用 `agent.version`。乐观锁的递增逻辑后续如需可在 Service 层实现，当前仅存储值。

- [ ] **Step 4: 运行所有测试**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/ -v`
预期输出: 全部测试 PASS。

- [x] **Step 5: Commit**

```bash
git add ai_service/repositories/agent_repository.py ai_service/tests/test_agent_api.py
git commit -m "feat(python): update PostgresAgentRepository create/update for new fields"
```

---

### Task 5: Python Repo — 添加 set_enabled 方法

**Files:**
- Modify: `ai_service/repositories/agent_repository.py`
- Test: `ai_service/tests/test_agent_api.py`

**Interfaces:**
- Produces: `AgentRepository.set_enabled(agent_id: str, enabled: bool) -> AgentDefinition | None`

- [ ] **Step 1: 写 set_enabled 测试**

在 `ai_service/tests/test_agent_api.py` 追加：

```python
@pytest.mark.asyncio
async def test_set_enabled(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    result = await repo.set_enabled(created.id, False)
    assert result is not None
    assert result.enabled is False
    # Verify it persists
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.enabled is False


@pytest.mark.asyncio
async def test_set_enabled_nonexistent_returns_none(repo: AgentRepository) -> None:
    result = await repo.set_enabled("nonexistent", True)
    assert result is None
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_set_enabled tests/test_agent_api.py::test_set_enabled_nonexistent_returns_none -v`
预期输出: FAIL — `AgentRepository` ABC 未定义 `set_enabled`。

- [ ] **Step 3: 实现 set_enabled**

在 `AgentRepository` ABC 中添加抽象方法：

```python
@abstractmethod
async def set_enabled(self, agent_id: str, enabled: bool) -> AgentDefinition | None: ...
```

在 `MockAgentRepository` 中添加实现：

```python
async def set_enabled(self, agent_id: str, enabled: bool) -> AgentDefinition | None:
    if agent_id not in self._agents:
        return None
    agent = self._agents[agent_id]
    agent.enabled = enabled
    return agent
```

在 `PostgresAgentRepository` 中添加实现：

```python
async def set_enabled(self, agent_id: str, enabled: bool) -> AgentDefinition | None:
    async with self._pool.connection() as conn:
        rows = await conn.execute(
            "UPDATE agent_definitions SET enabled = %s, updated_at = NOW() WHERE id = %s RETURNING *",
            (enabled, agent_id),
        )
        record = await rows.fetchone()
        if record is None:
            return None
        return _row_to_agent(record)
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_set_enabled tests/test_agent_api.py::test_set_enabled_nonexistent_returns_none -v`
预期输出: 两个测试 PASS。

- [x] **Step 5: Commit**

```bash
git add ai_service/repositories/agent_repository.py ai_service/tests/test_agent_api.py
git commit -m "feat(python): add set_enabled method to AgentRepository"
```

---

### Task 6: Python Repo — 添加 clone 方法

**Files:**
- Modify: `ai_service/repositories/agent_repository.py`
- Test: `ai_service/tests/test_agent_api.py`

**Interfaces:**
- Produces: `AgentRepository.clone(agent_id: str, created_by: str = "") -> AgentDefinition | None`

- [ ] **Step 1: 写 clone 测试**

在 `ai_service/tests/test_agent_api.py` 追加：

```python
@pytest.mark.asyncio
async def test_clone_basic(repo: AgentRepository, sample_agent: AgentDefinition) -> None:
    created = await repo.create(sample_agent)
    cloned = await repo.clone(created.id, created_by="tester")
    assert cloned is not None
    assert cloned.id != created.id
    assert cloned.display_name == created.display_name + " (Copy)"
    assert cloned.name == created.name + "-copy"
    assert cloned.is_builtin is False
    assert cloned.version == 1
    assert cloned.created_by == "tester"


@pytest.mark.asyncio
async def test_clone_nonexistent(repo: AgentRepository) -> None:
    result = await repo.clone("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_clone_name_conflict(repo: AgentRepository) -> None:
    agent = AgentDefinition(name="bot", display_name="Bot", system_prompt="...")
    await repo.create(agent)
    # Create a copy
    cloned1 = await repo.clone(agent.id)
    assert cloned1 is not None
    assert cloned1.name == "bot-copy"
    # Create another copy — should use numeric suffix
    cloned2 = await repo.clone(agent.id)
    assert cloned2 is not None
    assert cloned2.name == "bot-copy-2"
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_clone_basic tests/test_agent_api.py::test_clone_nonexistent tests/test_agent_api.py::test_clone_name_conflict -v`
预期输出: FAIL — `AgentRepository` ABC 未定义 `clone`。

- [ ] **Step 3: 在 AgentRepository ABC 中添加抽象方法**

```python
@abstractmethod
async def clone(self, agent_id: str, created_by: str = "") -> AgentDefinition | None: ...
```

- [ ] **Step 4: 在 MockAgentRepository 中实现 clone**

```python
async def clone(self, agent_id: str, created_by: str = "") -> AgentDefinition | None:
    if agent_id not in self._agents:
        return None
    source = self._agents[agent_id]
    new_id = uuid4().hex[:12]
    # Generate unique name
    base_name = source.name + "-copy"
    name = base_name
    suffix = 2
    while any(a.name == name for a in self._agents.values()):
        name = f"{base_name}-{suffix}"
        suffix += 1
    cloned = source.model_copy(deep=True)
    cloned.id = new_id
    cloned.name = name
    cloned.display_name = source.display_name + " (Copy)"
    cloned.is_builtin = False
    cloned.version = 1
    cloned.created_by = created_by
    self._agents[new_id] = cloned
    return cloned
```

注意：需要在文件顶部 import：`from uuid import uuid4`（如果尚未导入）。

- [ ] **Step 5: 在 PostgresAgentRepository 中实现 clone**

```python
async def clone(self, agent_id: str, created_by: str = "") -> AgentDefinition | None:
    async with self._pool.connection() as conn:
        # 1. SELECT source agent
        rows = await conn.execute(
            _AGENT_SELECT + " WHERE id = %s", (agent_id,)
        )
        record = await rows.fetchone()
        if record is None:
            return None
        source = _row_to_agent(record)

        # 2. Generate new id and name
        new_id = uuid4().hex[:12]
        base_name = source.name + "-copy"
        name = base_name

        # 3. Check for name conflicts
        suffix = 2
        while True:
            conflict = await conn.execute(
                "SELECT 1 FROM agent_definitions WHERE name = %s", (name,)
            )
            if await conflict.fetchone() is None:
                break
            name = f"{base_name}-{suffix}"
            suffix += 1

        # 4. INSERT cloned agent
        await conn.execute(
            """
            INSERT INTO agent_definitions (id, name, display_name, description,
                system_prompt, tools, model_config, trigger_keywords,
                collaboration_strategy, priority, enabled,
                icon, agent_type, avatar_url, is_builtin,
                tags, metadata, created_by, updated_by, version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                new_id, name, source.display_name + " (Copy)", source.description,
                source.system_prompt,
                _json.dumps(source.tools), _json.dumps(source.model_params),
                _json.dumps(source.trigger_keywords), source.collaboration_strategy,
                source.priority, source.enabled,
                source.icon, source.agent_type, source.avatar_url, False,
                _json.dumps(source.tags), _json.dumps(source.metadata),
                created_by, "", 1,
            ),
        )

        # 5. Fetch and return the new agent
        rows = await conn.execute(
            _AGENT_SELECT + " WHERE id = %s", (new_id,)
        )
        record = await rows.fetchone()
        assert record is not None  # We just inserted it
        return _row_to_agent(record)
```

注意：`from uuid import uuid4` 如果尚未在文件顶部导入，需要添加。

- [ ] **Step 6: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_clone_basic tests/test_agent_api.py::test_clone_nonexistent tests/test_agent_api.py::test_clone_name_conflict -v`
预期输出: 三个测试 PASS。

- [ ] **Step 7: Commit**

```bash
git add ai_service/repositories/agent_repository.py ai_service/tests/test_agent_api.py
git commit -m "feat(python): add clone method to AgentRepository"
```

---

### Task 7: Python API — 更新 create/update 读取 X-User

**Files:**
- Modify: `ai_service/api/routes/agents.py`
- Test: `ai_service/tests/test_agent_api.py`（新增 FastAPI TestClient 测试）

**Interfaces:**
- Consumes: `request.headers.get("X-User", "system")` 来自 FastAPI 请求
- Produces: `created_by`/`updated_by` 字段写入 AgentDefinition

- [ ] **Step 1: 写 X-User 测试**

在 `ai_service/tests/test_agent_api.py` 文件顶部添加导入：

```python
from fastapi.testclient import TestClient
```

在文件末尾追加：

```python
@pytest.fixture
def client(repo: AgentRepository) -> TestClient:
    # Override the repo in runtime
    from core.runtime import set_agent_repository
    set_agent_repository(repo)
    from main import app
    return TestClient(app)


@pytest.mark.asyncio
async def test_create_agent_sets_created_by(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agents/",
        json={
            "name": "xuser-test",
            "display_name": "X-User Test",
            "system_prompt": "Be helpful.",
        },
        headers={"X-User": "admin"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_by"] == "admin"


@pytest.mark.asyncio
async def test_create_agent_defaults_to_system(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agents/",
        json={
            "name": "no-header",
            "display_name": "No Header",
            "system_prompt": "Be helpful.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_by"] == "system"
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_create_agent_sets_created_by tests/test_agent_api.py::test_create_agent_defaults_to_system -v`
预期输出: FAIL — `created_by` 值为空字符串而非 "admin"/"system"。

- [ ] **Step 3: 更新 create_agent 和 update_agent 以读取 X-User**

在 `ai_service/api/routes/agents.py` 中，将现有的 `create_agent` 和 `update_agent` 函数更新为接收 `Request` 对象。修改文件顶部导入：

```python
from fastapi import APIRouter, HTTPException, Request
```

然后更新 `create_agent`：

```python
@router.post("/")
async def create_agent(agent: AgentDefinition, request: Request) -> AgentDefinition:
    repo = get_agent_repository()
    username = request.headers.get("X-User", "system")
    agent.created_by = username
    agent.updated_by = username
    return await repo.create(agent)
```

更新 `update_agent`：

```python
@router.put("/{agent_id}")
async def update_agent(agent_id: str, agent: AgentDefinition, request: Request) -> AgentDefinition:
    repo = get_agent_repository()
    username = request.headers.get("X-User", "system")
    agent.updated_by = username
    result = await repo.update(agent_id, agent)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_create_agent_sets_created_by tests/test_agent_api.py::test_create_agent_defaults_to_system -v`
预期输出: 两个测试 PASS。

- [x] **Step 5: Commit**

```bash
git add ai_service/api/routes/agents.py ai_service/tests/test_agent_api.py
git commit -m "feat(python): propagate X-User header to created_by/updated_by in create/update endpoints"
```

---

### Task 8: Python API — 添加 enable/disable 端点

**Files:**
- Modify: `ai_service/api/routes/agents.py`
- Test: `ai_service/tests/test_agent_api.py`

**Interfaces:**
- Produces: `POST /api/v1/agents/{agent_id}/enable` 和 `POST /api/v1/agents/{agent_id}/disable`

- [ ] **Step 1: 写 enable/disable 端点测试**

在 `ai_service/tests/test_agent_api.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_enable_agent(client: TestClient) -> None:
    # Create a disabled agent first
    create_resp = client.post(
        "/api/v1/agents/",
        json={
            "name": "to-enable",
            "display_name": "To Enable",
            "system_prompt": "...",
            "enabled": False,
        },
    )
    agent_id = create_resp.json()["id"]

    resp = client.post(f"/api/v1/agents/{agent_id}/enable", headers={"X-User": "admin"})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    assert resp.json()["updated_by"] == "admin"


@pytest.mark.asyncio
async def test_disable_agent(client: TestClient) -> None:
    create_resp = client.post(
        "/api/v1/agents/",
        json={
            "name": "to-disable",
            "display_name": "To Disable",
            "system_prompt": "...",
        },
    )
    agent_id = create_resp.json()["id"]

    resp = client.post(f"/api/v1/agents/{agent_id}/disable", headers={"X-User": "admin"})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


@pytest.mark.asyncio
async def test_enable_nonexistent_returns_404(client: TestClient) -> None:
    resp = client.post("/api/v1/agents/nonexistent/enable")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_disable_nonexistent_returns_404(client: TestClient) -> None:
    resp = client.post("/api/v1/agents/nonexistent/disable")
    assert resp.status_code == 404
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_enable_agent tests/test_agent_api.py::test_disable_agent tests/test_agent_api.py::test_enable_nonexistent_returns_404 tests/test_agent_api.py::test_disable_nonexistent_returns_404 -v`
预期输出: FAIL — 404，端点不存在。

- [ ] **Step 3: 实现 enable/disable 端点**

在 `ai_service/api/routes/agents.py` 中，在文件末尾添加：

```python
@router.post("/{agent_id}/enable")
async def enable_agent(agent_id: str, request: Request) -> AgentDefinition:
    repo = get_agent_repository()
    username = request.headers.get("X-User", "system")
    result = await repo.set_enabled(agent_id, True)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    result.updated_by = username
    # Persist the updated_by change
    await repo.update(agent_id, result)
    return result


@router.post("/{agent_id}/disable")
async def disable_agent(agent_id: str, request: Request) -> AgentDefinition:
    repo = get_agent_repository()
    username = request.headers.get("X-User", "system")
    result = await repo.set_enabled(agent_id, False)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    result.updated_by = username
    await repo.update(agent_id, result)
    return result
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_enable_agent tests/test_agent_api.py::test_disable_agent tests/test_agent_api.py::test_enable_nonexistent_returns_404 tests/test_agent_api.py::test_disable_nonexistent_returns_404 -v`
预期输出: 四个测试 PASS。

- [x] **Step 5: Commit**

```bash
git add ai_service/api/routes/agents.py ai_service/tests/test_agent_api.py
git commit -m "feat(python): add POST enable/disable endpoints for agents"
```

---

### Task 9: Python API — 添加 clone 端点

**Files:**
- Modify: `ai_service/api/routes/agents.py`
- Test: `ai_service/tests/test_agent_api.py`

**Interfaces:**
- Produces: `POST /api/v1/agents/{agent_id}/clone`

- [ ] **Step 1: 写 clone 端点测试**

在 `ai_service/tests/test_agent_api.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_clone_agent_endpoint(client: TestClient) -> None:
    create_resp = client.post(
        "/api/v1/agents/",
        json={
            "name": "source",
            "display_name": "Source Agent",
            "system_prompt": "Original.",
        },
    )
    agent_id = create_resp.json()["id"]

    resp = client.post(f"/api/v1/agents/{agent_id}/clone", headers={"X-User": "cloner"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] != agent_id
    assert data["name"] == "source-copy"
    assert data["display_name"] == "Source Agent (Copy)"
    assert data["created_by"] == "cloner"
    assert data["is_builtin"] is False


@pytest.mark.asyncio
async def test_clone_nonexistent_endpoint_returns_404(client: TestClient) -> None:
    resp = client.post("/api/v1/agents/nonexistent/clone")
    assert resp.status_code == 404
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_clone_agent_endpoint tests/test_agent_api.py::test_clone_nonexistent_endpoint_returns_404 -v`
预期输出: FAIL — 404，端点不存在。

- [ ] **Step 3: 实现 clone 端点**

在 `ai_service/api/routes/agents.py` 末尾追加：

```python
@router.post("/{agent_id}/clone")
async def clone_agent(agent_id: str, request: Request) -> AgentDefinition:
    repo = get_agent_repository()
    username = request.headers.get("X-User", "system")
    result = await repo.clone(agent_id, created_by=username)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/test_agent_api.py::test_clone_agent_endpoint tests/test_agent_api.py::test_clone_nonexistent_endpoint_returns_404 -v`
预期输出: 两个测试 PASS。

- [ ] **Step 5: 运行全部 Python 测试确认回归**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/ -v`
预期输出: 所有测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add ai_service/api/routes/agents.py ai_service/tests/test_agent_api.py
git commit -m "feat(python): add POST clone endpoint for agents"
```

---

### Task 10: SpringBoot — 添加 validation 依赖

**Files:**
- Modify: `backend/pom.xml`

- [ ] **Step 1: 在 pom.xml dependencies 末尾添加 validation starter**

在 `<dependencies>` 标签内，在 reactor-test 之后、`</dependencies>` 之前添加：

```xml
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
```

- [ ] **Step 2: 验证 Maven 依赖解析**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn dependency:resolve -q`
预期输出: BUILD SUCCESS，无错误。

- [ ] **Step 3: Commit**

```bash
git add backend/pom.xml
git commit -m "chore(backend): add spring-boot-starter-validation dependency"
```

---

### Task 11: SpringBoot — 创建 AgentRequest DTO

**Files:**
- Create: `backend/src/main/java/com/example/aichat/dto/AgentRequest.java`
- Create: `backend/src/test/java/com/example/aichat/dto/AgentRequestTest.java`

**Interfaces:**
- Produces: `AgentRequest` record，用于 Controller 输入绑定

- [ ] **Step 1: 创建 AgentRequest 测试**

创建目录（如不存在）：`backend/src/test/java/com/example/aichat/dto/`

```java
package com.example.aichat.dto;

import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class AgentRequestTest {

    private static Validator validator;

    @BeforeAll
    static void setUp() {
        try (ValidatorFactory factory = Validation.buildDefaultValidatorFactory()) {
            validator = factory.getValidator();
        }
    }

    @Test
    void validRequest_passesValidation() {
        AgentRequest req = new AgentRequest(
            "my-agent", "My Agent", "desc", "🤖", "assistant",
            "https://example.com/av.png", "You are helpful.",
            null, null, null, null, null, null, null
        );
        var violations = validator.validate(req);
        assertTrue(violations.isEmpty());
    }

    @Test
    void blankName_failsValidation() {
        AgentRequest req = new AgentRequest(
            "", "My Agent", null, null, null,
            null, "Be helpful.",
            null, null, null, null, null, null, null
        );
        var violations = validator.validate(req);
        assertFalse(violations.isEmpty());
    }

    @Test
    void blankDisplayName_failsValidation() {
        AgentRequest req = new AgentRequest(
            "agent", "", null, null, null,
            null, "Be helpful.",
            null, null, null, null, null, null, null
        );
        var violations = validator.validate(req);
        assertFalse(violations.isEmpty());
    }

    @Test
    void blankSystemPrompt_failsValidation() {
        AgentRequest req = new AgentRequest(
            "agent", "Agent", null, null, null,
            null, "",
            null, null, null, null, null, null, null
        );
        var violations = validator.validate(req);
        assertFalse(violations.isEmpty());
    }
}
```

- [ ] **Step 2: 运行测试确认编译失败**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test-compile -q`
预期输出: 编译错误 — AgentRequest 类不存在。

- [ ] **Step 3: 创建 AgentRequest record**

```java
package com.example.aichat.dto;

import jakarta.validation.constraints.NotBlank;

import java.util.List;
import java.util.Map;

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

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -pl . -Dtest=AgentRequestTest -q`
预期输出: BUILD SUCCESS，测试 PASS。

- [x] **Step 5: Commit**

```bash
git add backend/src/main/java/com/example/aichat/dto/AgentRequest.java backend/src/test/java/com/example/aichat/dto/AgentRequestTest.java
git commit -m "feat(backend): create AgentRequest DTO with validation annotations"
```

---

### Task 12: SpringBoot — 创建 AgentResponse DTO

**Files:**
- Create: `backend/src/main/java/com/example/aichat/dto/AgentResponse.java`
- Create: `backend/src/test/java/com/example/aichat/dto/AgentResponseTest.java`

**Interfaces:**
- Produces: `AgentResponse` record，用于 Controller 输出序列化

- [ ] **Step 1: 创建 AgentResponse 测试**

```java
package com.example.aichat.dto;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class AgentResponseTest {

    private final ObjectMapper mapper = new ObjectMapper()
        .registerModule(new JavaTimeModule());

    @Test
    void serializeAndDeserialize() throws JsonProcessingException {
        AgentResponse resp = new AgentResponse(
            "abc123", "test", "Test Agent", "desc",
            "🤖", "assistant", "https://ex.com/av.png", "Be helpful.",
            List.of("search"), Map.of("temperature", 0.7),
            List.of("help"), "sequential", 5, true, false,
            List.of("ai"), Map.of("tier", "premium"),
            "admin", "admin", 1,
            LocalDateTime.of(2024, 1, 1, 0, 0),
            LocalDateTime.of(2024, 1, 1, 0, 0)
        );

        String json = mapper.writeValueAsString(resp);
        assertTrue(json.contains("\"id\":\"abc123\""));
        assertTrue(json.contains("\"isBuiltin\":false"));
        assertTrue(json.contains("\"displayName\":\"Test Agent\""));

        AgentResponse deserialized = mapper.readValue(json, AgentResponse.class);
        assertEquals(resp.id(), deserialized.id());
        assertEquals(resp.displayName(), deserialized.displayName());
        assertEquals(resp.isBuiltin(), deserialized.isBuiltin());
        assertEquals(resp.tags(), deserialized.tags());
    }
}
```

- [ ] **Step 2: 运行测试确认编译失败**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test-compile -q`
预期输出: 编译错误 — AgentResponse 类不存在。

- [ ] **Step 3: 创建 AgentResponse record**

```java
package com.example.aichat.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

public record AgentResponse(
    String id,
    String name,
    @JsonProperty("display_name") String displayName,
    String description,
    String icon,
    @JsonProperty("agent_type") String agentType,
    @JsonProperty("avatar_url") String avatarUrl,
    @JsonProperty("system_prompt") String systemPrompt,
    List<String> tools,
    @JsonProperty("model_config") Map<String, Object> modelConfig,
    @JsonProperty("trigger_keywords") List<String> triggerKeywords,
    @JsonProperty("collaboration_strategy") String collaborationStrategy,
    Integer priority,
    Boolean enabled,
    @JsonProperty("is_builtin") Boolean isBuiltin,
    List<String> tags,
    Map<String, Object> metadata,
    @JsonProperty("created_by") String createdBy,
    @JsonProperty("updated_by") String updatedBy,
    Integer version,
    @JsonProperty("created_at") LocalDateTime createdAt,
    @JsonProperty("updated_at") LocalDateTime updatedAt
) {}
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentResponseTest -q`
预期输出: BUILD SUCCESS，测试 PASS。

- [x] **Step 5: Commit**

```bash
git add backend/src/main/java/com/example/aichat/dto/AgentResponse.java backend/src/test/java/com/example/aichat/dto/AgentResponseTest.java
git commit -m "feat(backend): create AgentResponse DTO with JSON mapping"
```

---

### Task 13: SpringBoot — 配置 agentWebClient Bean

**Files:**
- Modify: `backend/src/main/java/com/example/aichat/config/WebFluxConfig.java`

**Interfaces:**
- Produces: `agentWebClient` bean —— 带 X-User filter 的 WebClient 实例

- [ ] **Step 1: 为现有的 WebFluxConfig 添加 agentWebClient 方法**

```java
package com.example.aichat.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.util.retry.Retry;

import java.time.Duration;

@Configuration
public class WebFluxConfig {

    @Bean
    public WebClient webClient() {
        return WebClient.builder()
                .codecs(configurer ->
                        configurer.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
                .build();
    }

    @Bean
    public WebClient agentWebClient(
            @Value("${aichat.ai-service-url}") String baseUrl) {
        return WebClient.builder().baseUrl(baseUrl)
                .filter((request, next) -> {
                    String username = org.springframework.security.core.context
                            .ReactiveSecurityContextHolder.getContext()
                            .map(ctx -> ctx.getAuthentication().getName())
                            .defaultIfEmpty("system")
                            .block();
                    return next.exchange(
                            org.springframework.web.reactive.function.client
                                    .ClientRequest.from(request)
                                    .header("X-User", username)
                                    .build()
                    );
                })
                .codecs(c -> c.defaultCodecs().maxInMemorySize(16 * 1024 * 1024))
                .build();
    }
}
```

- [ ] **Step 2: 验证 Maven 编译**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn compile -q`
预期输出: BUILD SUCCESS。

- [ ] **Step 3: Commit**

```bash
git add backend/src/main/java/com/example/aichat/config/WebFluxConfig.java
git commit -m "feat(backend): add agentWebClient bean with X-User header injection"
```

---

### Task 14: SpringBoot — 创建 AgentClient（读取方法）

**Files:**
- Create: `backend/src/main/java/com/example/aichat/client/AgentClient.java`
- Create: `backend/src/test/java/com/example/aichat/client/AgentClientTest.java`

**Interfaces:**
- Consumes: `agentWebClient` bean, `AgentRequest`, `AgentResponse`
- Produces: `AgentClient.getById(id) -> Mono<AgentResponse>`, `AgentClient.listAll() -> Mono<List<AgentResponse>>`

- [ ] **Step 1: 写 listAll 和 getById 测试**

```java
package com.example.aichat.client;

import com.example.aichat.dto.AgentResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

import java.time.LocalDateTime;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class AgentClientTest {

    private WebClient webClient;
    private AgentClient agentClient;

    @BeforeEach
    void setUp() {
        webClient = WebClient.builder()
                .exchangeFunction(req ->
                        Mono.error(new RuntimeException("Not mocked"))
                )
                .build();
        agentClient = new AgentClient(webClient, "http://localhost:8000");
    }

    @Test
    void listAll_returnsAgents() {
        // We need a different approach: use a mock ExchangeFunction
        var exchangeFunction = mock(org.springframework.web.reactive.function.client.ExchangeFunction.class);
        webClient = WebClient.builder()
                .baseUrl("http://localhost:8000")
                .exchangeFunction(exchangeFunction)
                .build();
        agentClient = new AgentClient(webClient, "http://localhost:8000");

        AgentResponse agent = new AgentResponse(
            "1", "a", "A", null, null, null, null, "prompt",
            null, null, null, null, null, null, null,
            null, null, null, null, null, null, null
        );

        when(exchangeFunction.exchange(any()))
                .thenReturn(Mono.just(
                        org.springframework.web.reactive.function.client.ClientResponse.create(200)
                                .header("Content-Type", "application/json")
                                .body("[{\"id\":\"1\",\"name\":\"a\",\"display_name\":\"A\",\"system_prompt\":\"prompt\"}]")
                                .build()
                ));

        StepVerifier.create(agentClient.listAll())
                .expectNextMatches(list -> list.size() == 1 && list.getFirst().id().equals("1"))
                .verifyComplete();
    }

    @Test
    void getById_returnsAgent() {
        var exchangeFunction = mock(org.springframework.web.reactive.function.client.ExchangeFunction.class);
        webClient = WebClient.builder()
                .baseUrl("http://localhost:8000")
                .exchangeFunction(exchangeFunction)
                .build();
        agentClient = new AgentClient(webClient, "http://localhost:8000");

        when(exchangeFunction.exchange(any()))
                .thenReturn(Mono.just(
                        org.springframework.web.reactive.function.client.ClientResponse.create(200)
                                .header("Content-Type", "application/json")
                                .body("{\"id\":\"xyz\",\"name\":\"test\",\"display_name\":\"Test\",\"system_prompt\":\"prompt\"}")
                                .build()
                ));

        StepVerifier.create(agentClient.getById("xyz"))
                .expectNextMatches(a -> a.id().equals("xyz") && a.name().equals("test"))
                .verifyComplete();
    }
}
```

- [ ] **Step 2: 运行测试确认编译/运行失败**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentClientTest -q`
预期输出: 编译错误 — AgentClient 类不存在。

- [ ] **Step 3: 创建 AgentClient（listAll + getById）**

```java
package com.example.aichat.client;

import com.example.aichat.dto.AgentResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.List;

@Component
public class AgentClient {

    private final WebClient webClient;

    public AgentClient(WebClient agentWebClient,
                       @Value("${aichat.ai-service-url}") String baseUrl) {
        this.webClient = agentWebClient;
    }

    public Mono<List<AgentResponse>> listAll() {
        return webClient.get()
                .uri("/api/v1/agents/")
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<List<AgentResponse>>() {});
    }

    public Mono<AgentResponse> getById(String id) {
        return webClient.get()
                .uri("/api/v1/agents/{id}", id)
                .retrieve()
                .bodyToMono(AgentResponse.class);
    }
}
```

注意：构造函数接收 `agentWebClient` bean（Spring 按类型和名称自动装配），`baseUrl` 已在 WebClient bean 中配置，`@Value` 保留用于向下兼容。

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentClientTest -q`
预期输出: BUILD SUCCESS，测试 PASS。

- [x] **Step 5: Commit**

```bash
git add backend/src/main/java/com/example/aichat/client/AgentClient.java backend/src/test/java/com/example/aichat/client/AgentClientTest.java
git commit -m "feat(backend): create AgentClient with listAll and getById methods"
```

---

### Task 15: SpringBoot — AgentClient 添加写入方法

**Files:**
- Modify: `backend/src/main/java/com/example/aichat/client/AgentClient.java`
- Modify: `backend/src/test/java/com/example/aichat/client/AgentClientTest.java`

**Interfaces:**
- Produces: `AgentClient.create(req)`, `AgentClient.update(id, req)`, `AgentClient.delete(id)`

- [ ] **Step 1: 在 AgentClientTest 中追加写入方法测试**

```java
@Test
void create_returnsAgent() {
    var exchangeFunction = mock(org.springframework.web.reactive.function.client.ExchangeFunction.class);
    webClient = WebClient.builder()
            .baseUrl("http://localhost:8000")
            .exchangeFunction(exchangeFunction)
            .build();
    agentClient = new AgentClient(webClient, "http://localhost:8000");

    AgentRequest req = new AgentRequest(
        "new-agent", "New Agent", null, null, null,
        null, "Be helpful.", null, null, null, null, null, null, null
    );

    when(exchangeFunction.exchange(any()))
            .thenReturn(Mono.just(
                    org.springframework.web.reactive.function.client.ClientResponse.create(200)
                            .header("Content-Type", "application/json")
                            .body("{\"id\":\"new1\",\"name\":\"new-agent\",\"display_name\":\"New Agent\",\"system_prompt\":\"Be helpful.\"}")
                            .build()
            ));

    StepVerifier.create(agentClient.create(req))
            .expectNextMatches(a -> a.id().equals("new1") && a.name().equals("new-agent"))
            .verifyComplete();
}

@Test
void update_returnsAgent() {
    var exchangeFunction = mock(org.springframework.web.reactive.function.client.ExchangeFunction.class);
    webClient = WebClient.builder()
            .baseUrl("http://localhost:8000")
            .exchangeFunction(exchangeFunction)
            .build();
    agentClient = new AgentClient(webClient, "http://localhost:8000");

    AgentRequest req = new AgentRequest(
        "updated", "Updated", null, null, null,
        null, "New prompt.", null, null, null, null, null, null, null
    );

    when(exchangeFunction.exchange(any()))
            .thenReturn(Mono.just(
                    org.springframework.web.reactive.function.client.ClientResponse.create(200)
                            .header("Content-Type", "application/json")
                            .body("{\"id\":\"abc\",\"name\":\"updated\",\"display_name\":\"Updated\",\"system_prompt\":\"New prompt.\"}")
                            .build()
            ));

    StepVerifier.create(agentClient.update("abc", req))
            .expectNextMatches(a -> a.name().equals("updated"))
            .verifyComplete();
}

@Test
void delete_returnsVoid() {
    var exchangeFunction = mock(org.springframework.web.reactive.function.client.ExchangeFunction.class);
    webClient = WebClient.builder()
            .baseUrl("http://localhost:8000")
            .exchangeFunction(exchangeFunction)
            .build();
    agentClient = new AgentClient(webClient, "http://localhost:8000");

    when(exchangeFunction.exchange(any()))
            .thenReturn(Mono.just(
                    org.springframework.web.reactive.function.client.ClientResponse.create(200)
                            .build()
            ));

    StepVerifier.create(agentClient.delete("abc"))
            .verifyComplete();
}
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentClientTest#create_returnsAgent+AgentClientTest#update_returnsAgent+AgentClientTest#delete_returnsVoid -q`
预期输出: 编译错误 — AgentClient 没有这些方法。

- [ ] **Step 3: 在 AgentClient 中添加写入方法**

在 `AgentClient.java` 中追加：

```java
public Mono<AgentResponse> create(AgentRequest request) {
    return webClient.post()
            .uri("/api/v1/agents/")
            .bodyValue(request)
            .retrieve()
            .bodyToMono(AgentResponse.class);
}

public Mono<AgentResponse> update(String id, AgentRequest request) {
    return webClient.put()
            .uri("/api/v1/agents/{id}", id)
            .bodyValue(request)
            .retrieve()
            .bodyToMono(AgentResponse.class);
}

public Mono<Void> delete(String id) {
    return webClient.delete()
            .uri("/api/v1/agents/{id}", id)
            .retrieve()
            .bodyToMono(Void.class);
}
```

也需要在文件顶部添加 import：

```java
import com.example.aichat.dto.AgentRequest;
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentClientTest -q`
预期输出: BUILD SUCCESS，测试 PASS。

- [x] **Step 5: Commit**

```bash
git add backend/src/main/java/com/example/aichat/client/AgentClient.java backend/src/test/java/com/example/aichat/client/AgentClientTest.java
git commit -m "feat(backend): AgentClient add create, update, delete methods"
```

---

### Task 16: SpringBoot — AgentClient 添加操作方法

**Files:**
- Modify: `backend/src/main/java/com/example/aichat/client/AgentClient.java`
- Modify: `backend/src/test/java/com/example/aichat/client/AgentClientTest.java`

**Interfaces:**
- Produces: `AgentClient.enable(id)`, `AgentClient.disable(id)`, `AgentClient.clone(id)`

- [ ] **Step 1: 在 AgentClientTest 中追加操作方法测试**

```java
@Test
void enable_returnsAgent() {
    var exchangeFunction = mock(org.springframework.web.reactive.function.client.ExchangeFunction.class);
    webClient = WebClient.builder()
            .baseUrl("http://localhost:8000")
            .exchangeFunction(exchangeFunction)
            .build();
    agentClient = new AgentClient(webClient, "http://localhost:8000");

    when(exchangeFunction.exchange(any()))
            .thenReturn(Mono.just(
                    org.springframework.web.reactive.function.client.ClientResponse.create(200)
                            .header("Content-Type", "application/json")
                            .body("{\"id\":\"abc\",\"name\":\"test\",\"display_name\":\"Test\",\"system_prompt\":\"prompt\",\"enabled\":true}")
                            .build()
            ));

    StepVerifier.create(agentClient.enable("abc"))
            .expectNextMatches(a -> a.enabled() != null && a.enabled())
            .verifyComplete();
}

@Test
void disable_returnsAgent() {
    var exchangeFunction = mock(org.springframework.web.reactive.function.client.ExchangeFunction.class);
    webClient = WebClient.builder()
            .baseUrl("http://localhost:8000")
            .exchangeFunction(exchangeFunction)
            .build();
    agentClient = new AgentClient(webClient, "http://localhost:8000");

    when(exchangeFunction.exchange(any()))
            .thenReturn(Mono.just(
                    org.springframework.web.reactive.function.client.ClientResponse.create(200)
                            .header("Content-Type", "application/json")
                            .body("{\"id\":\"abc\",\"name\":\"test\",\"display_name\":\"Test\",\"system_prompt\":\"prompt\",\"enabled\":false}")
                            .build()
            ));

    StepVerifier.create(agentClient.disable("abc"))
            .expectNextMatches(a -> a.enabled() != null && !a.enabled())
            .verifyComplete();
}

@Test
void clone_returnsAgent() {
    var exchangeFunction = mock(org.springframework.web.reactive.function.client.ExchangeFunction.class);
    webClient = WebClient.builder()
            .baseUrl("http://localhost:8000")
            .exchangeFunction(exchangeFunction)
            .build();
    agentClient = new AgentClient(webClient, "http://localhost:8000");

    when(exchangeFunction.exchange(any()))
            .thenReturn(Mono.just(
                    org.springframework.web.reactive.function.client.ClientResponse.create(200)
                            .header("Content-Type", "application/json")
                            .body("{\"id\":\"new-id\",\"name\":\"test-copy\",\"display_name\":\"Test (Copy)\",\"system_prompt\":\"prompt\",\"is_builtin\":false}")
                            .build()
            ));

    StepVerifier.create(agentClient.clone("abc"))
            .expectNextMatches(a -> a.id().equals("new-id") && a.isBuiltin() != null && !a.isBuiltin())
            .verifyComplete();
}
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentClientTest -q`
预期输出: 编译错误 — AgentClient 没有 enable/disable/clone 方法。

- [ ] **Step 3: 在 AgentClient 中添加操作方法**

```java
public Mono<AgentResponse> enable(String id) {
    return webClient.post()
            .uri("/api/v1/agents/{id}/enable", id)
            .retrieve()
            .bodyToMono(AgentResponse.class);
}

public Mono<AgentResponse> disable(String id) {
    return webClient.post()
            .uri("/api/v1/agents/{id}/disable", id)
            .retrieve()
            .bodyToMono(AgentResponse.class);
}

public Mono<AgentResponse> clone(String id) {
    return webClient.post()
            .uri("/api/v1/agents/{id}/clone", id)
            .retrieve()
            .bodyToMono(AgentResponse.class);
}
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentClientTest -q`
预期输出: BUILD SUCCESS，所有 AgentClient 测试 PASS。

- [x] **Step 5: Commit**

```bash
git add backend/src/main/java/com/example/aichat/client/AgentClient.java backend/src/test/java/com/example/aichat/client/AgentClientTest.java
git commit -m "feat(backend): AgentClient add enable, disable, clone methods"
```

---

### Task 17: SpringBoot — 创建 AgentService

**Files:**
- Create: `backend/src/main/java/com/example/aichat/service/AgentService.java`
- Create: `backend/src/test/java/com/example/aichat/service/AgentServiceTest.java`

**Interfaces:**
- Consumes: `AgentClient`, `AgentRequest`, `AgentResponse`
- Produces: `AgentService` —— 8 个公开方法，日志记录

- [ ] **Step 1: 写 AgentService 测试（使用 mock AgentClient）**

```java
package com.example.aichat.service;

import com.example.aichat.client.AgentClient;
import com.example.aichat.dto.AgentRequest;
import com.example.aichat.dto.AgentResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AgentServiceTest {

    @Mock
    private AgentClient agentClient;

    private AgentService agentService;

    @BeforeEach
    void setUp() {
        agentService = new AgentService(agentClient);
    }

    @Test
    void listAll_delegatesToClient() {
        when(agentClient.listAll()).thenReturn(Mono.just(List.of()));
        StepVerifier.create(agentService.listAll())
                .expectNextMatches(list -> list.isEmpty())
                .verifyComplete();
    }

    @Test
    void getById_delegatesToClient() {
        AgentResponse expected = new AgentResponse(
            "id1", "name", "display", null, null, null, null, "prompt",
            null, null, null, null, null, null, null,
            null, null, null, null, null, null, null
        );
        when(agentClient.getById("id1")).thenReturn(Mono.just(expected));

        StepVerifier.create(agentService.getById("id1"))
                .expectNext(expected)
                .verifyComplete();
    }

    @Test
    void create_delegatesToClient() {
        AgentRequest req = new AgentRequest(
            "a", "A", null, null, null, null, "prompt",
            null, null, null, null, null, null, null
        );
        when(agentClient.create(req)).thenReturn(Mono.just(
            new AgentResponse("new", "a", "A", null, null, null, null, "prompt",
                null, null, null, null, null, null, null,
                null, null, null, null, null, null, null)
        ));

        StepVerifier.create(agentService.create(req))
                .expectNextMatches(r -> r.id().equals("new"))
                .verifyComplete();
    }

    @Test
    void enable_delegatesToClient() {
        when(agentClient.enable("abc")).thenReturn(Mono.just(
            new AgentResponse("abc", "a", "A", null, null, null, null, "prompt",
                null, null, null, null, null, true, null,
                null, null, null, null, null, null, null)
        ));

        StepVerifier.create(agentService.enable("abc"))
                .expectNextMatches(r -> r.enabled() != null && r.enabled())
                .verifyComplete();
    }

    @Test
    void clone_delegatesToClient() {
        when(agentClient.clone("abc")).thenReturn(Mono.just(
            new AgentResponse("clone-id", "a-copy", "A (Copy)", null, null, null, null, "prompt",
                null, null, null, null, null, null, false,
                null, null, null, null, null, null, null)
        ));

        StepVerifier.create(agentService.clone("abc"))
                .expectNextMatches(r -> r.id().equals("clone-id") && r.isBuiltin() == false)
                .verifyComplete();
    }
}
```

- [ ] **Step 2: 运行测试确认编译失败**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test-compile -q`
预期输出: 编译错误 — AgentService 类不存在。

- [ ] **Step 3: 创建 AgentService 类**

```java
package com.example.aichat.service;

import com.example.aichat.client.AgentClient;
import com.example.aichat.dto.AgentRequest;
import com.example.aichat.dto.AgentResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

import java.util.List;

@Service
public class AgentService {

    private static final Logger log = LoggerFactory.getLogger(AgentService.class);

    private final AgentClient agentClient;

    public AgentService(AgentClient agentClient) {
        this.agentClient = agentClient;
    }

    public Mono<List<AgentResponse>> listAll() {
        log.info("Listing all agents");
        return agentClient.listAll()
                .doOnSuccess(agents -> log.info("Listed {} agents", agents.size()));
    }

    public Mono<AgentResponse> getById(String id) {
        log.info("Getting agent by id: {}", id);
        return agentClient.getById(id)
                .doOnSuccess(a -> log.info("Found agent: {}", id));
    }

    public Mono<AgentResponse> create(AgentRequest request) {
        log.info("Creating agent: {}", request.name());
        return agentClient.create(request)
                .doOnSuccess(a -> log.info("Created agent: {}", a.id()));
    }

    public Mono<AgentResponse> update(String id, AgentRequest request) {
        log.info("Updating agent: {}", id);
        return agentClient.update(id, request)
                .doOnSuccess(a -> log.info("Updated agent: {}", id));
    }

    public Mono<Void> delete(String id) {
        log.info("Deleting agent: {}", id);
        return agentClient.delete(id)
                .doOnSuccess(v -> log.info("Deleted agent: {}", id));
    }

    public Mono<AgentResponse> enable(String id) {
        log.info("Enabling agent: {}", id);
        return agentClient.enable(id)
                .doOnSuccess(a -> log.info("Enabled agent: {}", id));
    }

    public Mono<AgentResponse> disable(String id) {
        log.info("Disabling agent: {}", id);
        return agentClient.disable(id)
                .doOnSuccess(a -> log.info("Disabled agent: {}", id));
    }

    public Mono<AgentResponse> clone(String id) {
        log.info("Cloning agent: {}", id);
        return agentClient.clone(id)
                .doOnSuccess(a -> log.info("Cloned agent {} to {}", id, a.id()));
    }
}
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentServiceTest -q`
预期输出: BUILD SUCCESS，AgentService 测试 PASS。

- [x] **Step 5: Commit**

```bash
git add backend/src/main/java/com/example/aichat/service/AgentService.java backend/src/test/java/com/example/aichat/service/AgentServiceTest.java
git commit -m "feat(backend): create AgentService with logging and CRUD delegation"
```

---

### Task 18: SpringBoot — AgentService 异常处理

**Files:**
- Modify: `backend/src/main/java/com/example/aichat/service/AgentService.java`
- Modify: `backend/src/test/java/com/example/aichat/service/AgentServiceTest.java`

**Interfaces:**
- Produces: `WebClientRequestException` → 503, `ConnectException` → 503, 4xx/5xx 原样传播

- [ ] **Step 1: 写异常处理测试**

在 `AgentServiceTest.java` 中追加：

```java
import org.springframework.web.reactive.function.client.WebClientRequestException;
import java.net.ConnectException;

// 在类内部追加：

@Test
void connectionError_returns503() {
    when(agentClient.listAll()).thenReturn(
        Mono.error(new WebClientRequestException(
            new ConnectException("Connection refused"),
            "POST", null, null
        ))
    );

    StepVerifier.create(agentService.listAll())
            .expectErrorMatches(e ->
                e instanceof com.example.aichat.exception.ServiceUnavailableException
                && e.getMessage().contains("AI 服务不可用")
            )
            .verify();
}

@Test
void clientError_propagatesAsIs() {
    when(agentClient.getById("404")).thenReturn(
        Mono.error(new org.springframework.web.reactive.function.client.WebClientResponseException(
            404, "Not Found", null, null, null
        ))
    );

    StepVerifier.create(agentService.getById("404"))
            .expectError(org.springframework.web.reactive.function.client.WebClientResponseException.class)
            .verify();
}
```

- [ ] **Step 2: 创建 ServiceUnavailableException 类**

在 `backend/src/main/java/com/example/aichat/exception/` 目录下创建 `ServiceUnavailableException.java`：

```java
package com.example.aichat.exception;

public class ServiceUnavailableException extends RuntimeException {
    public ServiceUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }

    public ServiceUnavailableException(String message) {
        super(message);
    }
}
```

- [ ] **Step 3: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentServiceTest#connectionError_returns503+AgentServiceTest#clientError_propagatesAsIs -q`
预期输出: FAIL — AgentService 尚未处理异常。

- [ ] **Step 4: 在 AgentService 中添加异常处理辅助方法**

在 `AgentService` 类中添加：

```java
import org.springframework.web.reactive.function.client.WebClientRequestException;
import com.example.aichat.exception.ServiceUnavailableException;

// 在类中添加辅助方法：

private <T> Mono<T> handleClientError(Throwable error) {
    if (error instanceof WebClientRequestException) {
        return Mono.error(new ServiceUnavailableException("AI 服务不可用，请稍后再试", error));
    }
    return Mono.error(error);
}
```

然后在每个方法中添加 `.onErrorResume(this::handleClientError)`。例如 `listAll()`：

```java
public Mono<List<AgentResponse>> listAll() {
    log.info("Listing all agents");
    return agentClient.listAll()
            .doOnSuccess(agents -> log.info("Listed {} agents", agents.size()))
            .onErrorResume(this::handleClientError);
}
```

对其他 7 个方法同样添加 `.onErrorResume(this::handleClientError)`。

- [ ] **Step 5: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentServiceTest -q`
预期输出: BUILD SUCCESS，所有 AgentServiceTest 测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/src/main/java/com/example/aichat/service/AgentService.java \
      backend/src/main/java/com/example/aichat/exception/ServiceUnavailableException.java \
      backend/src/test/java/com/example/aichat/service/AgentServiceTest.java
git commit -m "feat(backend): AgentService exception handling — connection errors to 503"
```

---

### Task 19: SpringBoot — 重写 AgentController GET 端点

**Files:**
- Modify: `backend/src/main/java/com/example/aichat/controller/AgentController.java`
- Create: `backend/src/test/java/com/example/aichat/controller/AgentControllerTest.java`

**Interfaces:**
- Consumes: `AgentService`
- Produces: `GET /api/agents/` 和 `GET /api/agents/{id}` 端点，返回 `List<AgentResponse>` / `AgentResponse`

- [ ] **Step 1: 写 Controller GET 端点测试**

```java
package com.example.aichat.controller;

import com.example.aichat.dto.AgentResponse;
import com.example.aichat.service.AgentService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.WebFluxTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Mono;

import java.util.List;

import static org.mockito.Mockito.when;

@WebFluxTest(AgentController.class)
class AgentControllerTest {

    @Autowired
    private WebTestClient webTestClient;

    @MockitoBean
    private AgentService agentService;

    @Test
    void listAgents_returnsList() {
        when(agentService.listAll()).thenReturn(Mono.just(List.of(
            new AgentResponse("1", "a", "A", null, null, null, null, "prompt",
                null, null, null, null, null, null, null,
                null, null, null, null, null, null, null)
        )));

        webTestClient.get().uri("/api/agents/")
                .exchange()
                .expectStatus().isOk()
                .expectBodyList(AgentResponse.class)
                .hasSize(1);
    }

    @Test
    void getById_returnsAgent() {
        when(agentService.getById("1")).thenReturn(Mono.just(
            new AgentResponse("1", "a", "A", null, null, null, null, "prompt",
                null, null, null, null, null, null, null,
                null, null, null, null, null, null, null)
        ));

        webTestClient.get().uri("/api/agents/1")
                .exchange()
                .expectStatus().isOk()
                .expectBody(AgentResponse.class)
                .matches(r -> r.id().equals("1"));
    }

    @Test
    void getById_notFound_returns404() {
        when(agentService.getById("nonexistent")).thenReturn(
            Mono.error(new org.springframework.web.reactive.function.client.WebClientResponseException(
                404, "Not Found", null, null, null
            ))
        );

        webTestClient.get().uri("/api/agents/nonexistent")
                .exchange()
                .expectStatus().is4xxClientError();
    }
}
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentControllerTest -q`
预期输出: 编译失败或测试失败 — 旧的 AgentController 使用 `String` 而非 `AgentService`。

- [ ] **Step 3: 重写 AgentController**

```java
package com.example.aichat.controller;

import com.example.aichat.dto.AgentRequest;
import com.example.aichat.dto.AgentResponse;
import com.example.aichat.service.AgentService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.List;

@RestController
@RequestMapping("/api/agents")
public class AgentController {

    private final AgentService agentService;

    public AgentController(AgentService agentService) {
        this.agentService = agentService;
    }

    @GetMapping
    public Mono<ResponseEntity<List<AgentResponse>>> listAgents() {
        return agentService.listAll()
                .map(ResponseEntity::ok);
    }

    @GetMapping("/{id}")
    public Mono<ResponseEntity<AgentResponse>> getAgent(@PathVariable String id) {
        return agentService.getById(id)
                .map(ResponseEntity::ok)
                .onErrorResume(
                    org.springframework.web.reactive.function.client.WebClientResponseException.class,
                    e -> Mono.just(ResponseEntity.status(e.getStatusCode()).build())
                );
    }
}
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentControllerTest -q`
预期输出: BUILD SUCCESS，测试 PASS。

- [x] **Step 5: Commit**

```bash
git add backend/src/main/java/com/example/aichat/controller/AgentController.java \
      backend/src/test/java/com/example/aichat/controller/AgentControllerTest.java
git commit -m "feat(backend): rewrite AgentController with GET list and detail endpoints"
```

---

### Task 20: SpringBoot — AgentController 添加 POST/PUT/DELETE

**Files:**
- Modify: `backend/src/main/java/com/example/aichat/controller/AgentController.java`
- Modify: `backend/src/test/java/com/example/aichat/controller/AgentControllerTest.java`

- [ ] **Step 1: 在 ControllerTest 中追加写入端点测试**

```java
@Test
void createAgent_returnsCreated() {
    AgentRequest req = new AgentRequest(
        "new", "New", null, null, null, null, "prompt",
        null, null, null, null, null, null, null
    );
    AgentResponse resp = new AgentResponse(
        "new-id", "new", "New", null, null, null, null, "prompt",
        null, null, null, null, null, null, null,
        null, null, null, null, null, null, null
    );

    when(agentService.create(req)).thenReturn(Mono.just(resp));

    webTestClient.post().uri("/api/agents/")
            .bodyValue(req)
            .exchange()
            .expectStatus().isOk()
            .expectBody(AgentResponse.class)
            .matches(r -> r.id().equals("new-id"));
}

@Test
void updateAgent_returnsUpdated() {
    AgentRequest req = new AgentRequest(
        "updated", "Updated", null, null, null, null, "new prompt",
        null, null, null, null, null, null, null
    );
    AgentResponse resp = new AgentResponse(
        "id1", "updated", "Updated", null, null, null, null, "new prompt",
        null, null, null, null, null, null, null,
        null, null, null, null, null, null, null
    );

    when(agentService.update("id1", req)).thenReturn(Mono.just(resp));

    webTestClient.put().uri("/api/agents/id1")
            .bodyValue(req)
            .exchange()
            .expectStatus().isOk()
            .expectBody(AgentResponse.class)
            .matches(r -> r.name().equals("updated"));
}

@Test
void deleteAgent_returnsOk() {
    when(agentService.delete("id1")).thenReturn(Mono.empty());

    webTestClient.delete().uri("/api/agents/id1")
            .exchange()
            .expectStatus().isOk();
}
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentControllerTest -q`
预期输出: 测试失败 — Controller 缺少这些端点。

- [ ] **Step 3: 在 AgentController 中添加 POST/PUT/DELETE 端点**

```java
@PostMapping
public Mono<ResponseEntity<AgentResponse>> createAgent(
        @Valid @RequestBody AgentRequest request) {
    return agentService.create(request)
            .map(ResponseEntity::ok);
}

@PutMapping("/{id}")
public Mono<ResponseEntity<AgentResponse>> updateAgent(
        @PathVariable String id,
        @Valid @RequestBody AgentRequest request) {
    return agentService.update(id, request)
            .map(ResponseEntity::ok);
}

@DeleteMapping("/{id}")
public Mono<ResponseEntity<Void>> deleteAgent(@PathVariable String id) {
    return agentService.delete(id)
            .then(Mono.just(ResponseEntity.ok().<Void>build()));
}
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentControllerTest -q`
预期输出: BUILD SUCCESS，测试 PASS。

- [x] **Step 5: Commit**

```bash
git add backend/src/main/java/com/example/aichat/controller/AgentController.java \
      backend/src/test/java/com/example/aichat/controller/AgentControllerTest.java
git commit -m "feat(backend): AgentController add POST, PUT, DELETE endpoints"
```

---

### Task 21: SpringBoot — AgentController 添加操作方法端点

**Files:**
- Modify: `backend/src/main/java/com/example/aichat/controller/AgentController.java`
- Modify: `backend/src/test/java/com/example/aichat/controller/AgentControllerTest.java`

- [ ] **Step 1: 在 ControllerTest 中追加操作测试**

```java
@Test
void enableAgent_returnsEnabled() {
    AgentResponse resp = new AgentResponse(
        "id1", "a", "A", null, null, null, null, "prompt",
        null, null, null, null, null, true, null,
        null, null, null, null, null, null, null
    );

    when(agentService.enable("id1")).thenReturn(Mono.just(resp));

    webTestClient.post().uri("/api/agents/id1/enable")
            .exchange()
            .expectStatus().isOk()
            .expectBody(AgentResponse.class)
            .matches(r -> r.enabled() != null && r.enabled());
}

@Test
void disableAgent_returnsDisabled() {
    AgentResponse resp = new AgentResponse(
        "id1", "a", "A", null, null, null, null, "prompt",
        null, null, null, null, null, false, null,
        null, null, null, null, null, null, null
    );

    when(agentService.disable("id1")).thenReturn(Mono.just(resp));

    webTestClient.post().uri("/api/agents/id1/disable")
            .exchange()
            .expectStatus().isOk()
            .expectBody(AgentResponse.class)
            .matches(r -> r.enabled() != null && !r.enabled());
}

@Test
void cloneAgent_returnsCloned() {
    AgentResponse resp = new AgentResponse(
        "clone-id", "a-copy", "A (Copy)", null, null, null, null, "prompt",
        null, null, null, null, null, null, false,
        null, null, null, null, null, null, null
    );

    when(agentService.clone("id1")).thenReturn(Mono.just(resp));

    webTestClient.post().uri("/api/agents/id1/clone")
            .exchange()
            .expectStatus().isOk()
            .expectBody(AgentResponse.class)
            .matches(r -> r.id().equals("clone-id") && r.isBuiltin() == false);
}
```

- [x] **Step 2: 运行测试确认失败**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentControllerTest -q`
预期输出: 测试失败 — Controller 缺少 enable/disable/clone 端点。

- [ ] **Step 3: 在 AgentController 中添加操作方法端点**

```java
@PostMapping("/{id}/enable")
public Mono<ResponseEntity<AgentResponse>> enableAgent(@PathVariable String id) {
    return agentService.enable(id)
            .map(ResponseEntity::ok);
}

@PostMapping("/{id}/disable")
public Mono<ResponseEntity<AgentResponse>> disableAgent(@PathVariable String id) {
    return agentService.disable(id)
            .map(ResponseEntity::ok);
}

@PostMapping("/{id}/clone")
public Mono<ResponseEntity<AgentResponse>> cloneAgent(@PathVariable String id) {
    return agentService.clone(id)
            .map(ResponseEntity::ok);
}
```

- [x] **Step 4: 运行测试确认通过**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -Dtest=AgentControllerTest -q`
预期输出: BUILD SUCCESS，所有 Controller 测试 PASS。

- [ ] **Step 5: 运行全部后端测试确认回归**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn test -q`
预期输出: BUILD SUCCESS，所有 SpringBoot 测试 PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/src/main/java/com/example/aichat/controller/AgentController.java \
      backend/src/test/java/com/example/aichat/controller/AgentControllerTest.java
git commit -m "feat(backend): AgentController add enable, disable, clone endpoints"
```

---

### Task 22: 集成验证

**Files:**
- 无新代码，全栈手动验证

- [ ] **Step 1: 应用数据库迁移**

运行: `psql postgresql://localhost:5432/ai_chat -f ai_service/db/migrations/V003__agent_upgrade.sql`
预期输出: ALTER TABLE + UPDATE 5 均成功。

验证方式: 运行 `psql postgresql://localhost:5432/ai_chat -c "\d agent_definitions"`，确认 20 列全部存在。

- [ ] **Step 2: 启动 Python FastAPI 服务**

运行: `cd /Volumes/work/projects/winter-agent/ai_service && uvicorn main:app --port 8000`

- [ ] **Step 3: 验证 Python 新端点**

启用测试:
```bash
curl -X POST http://localhost:8000/api/v1/agents/srch-agent/enable -H "X-User: admin"
```
预期输出: 200，`"enabled": true`，`"updated_by": "admin"`

禁用测试:
```bash
curl -X POST http://localhost:8000/api/v1/agents/srch-agent/disable -H "X-User: admin"
```
预期输出: 200，`"enabled": false`

克隆测试:
```bash
curl -X POST http://localhost:8000/api/v1/agents/srch-agent/clone -H "X-User: admin"
```
预期输出: 200，`"name": "search-copy"`，`"display_name": "🔍 搜索助手 (Copy)"`，`"is_builtin": false`

不存在 Agent 测试:
```bash
curl -X POST http://localhost:8000/api/v1/agents/nonexistent/enable
```
预期输出: 404

- [ ] **Step 4: 启动 SpringBoot 后端并验证代理端点**

运行: `cd /Volumes/work/projects/winter-agent/backend && mvn spring-boot:run`

```bash
# 先登录获取 JWT
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin123"}' | jq -r '.token')

# 列出所有 Agent
curl -s http://localhost:8080/api/agents/ -H "Authorization: Bearer $TOKEN" | jq '. | length'
# 预期: 输出 Agent 数量（至少 5 个种子 Agent）

# 获取单个 Agent
curl -s http://localhost:8080/api/agents/srch-agent -H "Authorization: Bearer $TOKEN" | jq '.name'
# 预期: "search"

# 启用/禁用
curl -X POST http://localhost:8080/api/agents/srch-agent/disable -H "Authorization: Bearer $TOKEN"
# 预期: 200

# 克隆
curl -X POST http://localhost:8080/api/agents/srch-agent/clone -H "Authorization: Bearer $TOKEN"
# 预期: 返回克隆后的 Agent
```

- [ ] **Step 5: 验证现有 Chat SSE 流程不受影响**

```bash
# 发送聊天消息（使用原有 SSE 流程）
curl -N -X POST http://localhost:8080/api/chat \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"message":"你好","agentId":"general","conversationId":"test-conv","messageId":"test-msg"}'
```
预期输出: SSE 事件流正常返回，不受代理变更影响。

- [ ] **Step 6: 运行两侧项目完整测试套件**

Python:
```bash
cd /Volumes/work/projects/winter-agent/ai_service && python -m pytest tests/ -v
```
预期输出: 所有测试 PASS。

SpringBoot:
```bash
cd /Volumes/work/projects/winter-agent/backend && mvn test -q
```
预期输出: BUILD SUCCESS。

- [ ] **Step 7: Commit（如果过程中有任何修复）**

```bash
git add -A
git commit -m "chore: final verification and fixes for agent-backend-proxy"
```

---

## 自检清单

### 1. 设计覆盖检查

| 设计文档要求 | 对应任务 |
|---|---|
| PostgreSQL 9 新增列 | Task 1 |
| 种子 Agent 回填 is_builtin | Task 1 |
| AgentDefinition 模型扩展 9 字段 | Task 2 |
| `_row_to_agent` 和 SQL 常量更新 | Task 3 |
| create/update 支持新字段 | Task 4 |
| `set_enabled()` 仓库方法 | Task 5 |
| `clone()` 仓库方法 | Task 6 |
| `X-User` header 传播到 created_by/updated_by | Task 7 |
| `POST /enable` 和 `POST /disable` 端点 | Task 8 |
| `POST /clone` 端点 | Task 9 |
| AgentRequest DTO（@Validated） | Task 11 |
| AgentResponse DTO（JSON 映射） | Task 12 |
| agentWebClient bean（X-User filter） | Task 13 |
| AgentClient 8 个方法 | Task 14-16 |
| AgentService 日志 + 异常转换 | Task 17-18 |
| AgentController 8 个端点 | Task 19-21 |
| 兼容性保证（Runtime、SSE 不动） | Task 22 验证步骤 5 |
| 错误处理策略（503/404/400） | Task 18, 21 |

### 2. 占位符检查

所有任务均包含完整代码和测试，无 TBD、TODO 或 "implement later"。

### 3. 类型一致性检查

| 类型/签名 | 定义位置 | 引用位置 | 一致性 |
|---|---|---|---|
| `AgentDefinition` 新字段 | Task 2 | Tasks 3-9 | 一致 |
| `set_enabled(agent_id, enabled) -> AgentDefinition\|None` | Task 5 | Task 8 | 一致 |
| `clone(agent_id, created_by) -> AgentDefinition\|None` | Task 6 | Task 9 | 一致 |
| `AgentRequest` record | Task 11 | Tasks 15, 17, 20 | 一致 |
| `AgentResponse` record | Task 12 | Tasks 14-21 | 一致 |
| `AgentClient.*` 方法签名 | Tasks 14-16 | Tasks 17-21 | 一致 |
| `AgentService.*` 方法签名 | Tasks 17-18 | Tasks 19-21 | 一致 |

---

## 执行交接

计划完整，包含 **9 组共 22 个可执行任务**，按依赖顺序排列：PostgreSQL -> Python Model -> Python Repo -> Python API -> SpringBoot DTO -> SpringBoot Client -> SpringBoot Service -> SpringBoot Controller -> Verification。

每个任务遵循 TDD 循环（写测试 -> 运行失败 -> 实现 -> 运行通过 -> commit），可在 1 小时内完成。任务之间通过精确接口签名连接，可并行或串行执行。

**两种执行方式可选：**

**1. Subagent-Driven（推荐）** - 每个任务分派新的 subagent，任务间做 review，快速迭代。使用 `superpowers:subagent-driven-development` 技能。

**2. Inline Execution** - 在当前会话中使用 `superpowers:executing-plans` 技能执行，批量执行含检查点。

请问选择哪种方式？

---

### Critical Files for Implementation

- `/Volumes/work/projects/winter-agent/ai_service/models/agent.py` — Python Pydantic 模型扩展，所有下游依赖于此
- `/Volumes/work/projects/winter-agent/ai_service/repositories/agent_repository.py` — Repository 层核心，包含 set_enabled/clone 方法和 SQL 变更
- `/Volumes/work/projects/winter-agent/backend/src/main/java/com/example/aichat/client/AgentClient.java` — SpringBoot 侧 HTTP 通信核心，8 个方法覆盖所有操作
- `/Volumes/work/projects/winter-agent/backend/src/main/java/com/example/aichat/controller/AgentController.java` — 最终用户入口，需要完整重写
- `/Volumes/work/projects/winter-agent/ai_service/db/migrations/V003__agent_upgrade.sql` — 数据库迁移，所有新功能的数据基础