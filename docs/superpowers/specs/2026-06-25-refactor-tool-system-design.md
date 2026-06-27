---
comet_change: refactor-tool-system
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-25-refactor-tool-system
status: final
---

# Tool System Refactor — Design Doc

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│  ToolRegistry.discover()  ← 启动时扫描 tools/ 目录          │
│  ToolRegistry.build_tools_prompt()  →  LLM prompt           │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐   ┌─────────┐   ┌──────────┐
   │SearchTool│   │TimeTool │   │SandboxTool│  ← @tool 装饰器
   │ @tool   │   │ @tool   │   │ @tool    │
   └─────────┘   └─────────┘   └──────────┘
                       │
              BaseTool (ABC)
              ├── name: str
              ├── description: str
              ├── schema: ToolSchema
              └── execute(input) → ToolResult
```

## Component Design

### 1. ToolSchema + @tool decorator (`tools/schema.py`)

```python
class ToolSchema(BaseModel):
    """OpenAI function schema for a tool's input parameters."""
    parameters: dict  # JSON Schema: {type, required, properties}

def tool(cls):
    """Decorator: marks a BaseTool subclass for auto-discovery."""
    cls._is_tool = True
    return cls
```

`ToolRegistry` 在 `discover()` 时遍历 `BaseTool.__subclasses__()`，收集带 `_is_tool=True` 且 `schema` 完整（name + description + schema.parameters）的子类。

### 2. ToolRegistry 启动流程

```
main.py lifespan:
  1. pool ← AsyncConnectionPool(conninfo=...)
  2. checkpointer ← AsyncPostgresSaver(pool)
  3. registry ← ToolRegistry()
  4. registry.discover()  ← 自动发现所有 @tool 类
  5. set_tool_registry(registry)
  6. print(registry.list_tools())  → ['search','time','browser','execute_python']
```

`discover()` 逻辑：
1. `import tools` — 触发所有子包的 `__init__.py` 执行，导入所有工具模块
2. `BaseTool.__subclasses__()` — 遍历所有子类
3. 过滤 `_is_tool=True` + schema 完整
4. 调用 `register(instance)` 存入 `self._tools`

### 3. agent_node 并行协议

JSON Mode 输出格式同时兼容两种：

```python
# 单工具（向后兼容）
{"action": "tool", "tool": "search", "query": "..."}

# 并行多工具
{"actions": [
    {"tool": "search", "query": "GDP 2024"},
    {"tool": "time", "query": ""}
]}
```

agent_node 解析逻辑：
- 检测 `actions` 数组 → 走并行路径（最多 3 个）
- 检测 `action` 字段 → 走单工具路径（向后兼容）
- 都不是 → `final_answer` 路径

### 4. tool_node 并行执行

```python
if "actions" in tool_input:
    tasks = [registry.invoke_capability(CapabilityCall(a["tool"], {"query": a["query"]}))
             for a in tool_input["actions"][:3]]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # 合并结果，error 隔离
else:
    # 单工具路径（原有逻辑）
```

### 5. Pyodide Code Sandbox

```python
@tool
class CodeSandboxTool(BaseTool):
    name = "execute_python"
    description = "Execute Python code for data analysis"
    schema = ToolSchema(parameters={
        "type": "object",
        "required": ["code"],
        "properties": {
            "code": {"type": "string", "description": "Python code"},
            "timeout": {"type": "integer", "default": 30}
        }
    })

    async def execute(self, input: dict) -> ToolResult:
        # 在线程池中运行 Pyodide（同步 API）
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _sandbox_pool, _run_pyodide, input["code"], input.get("timeout", 30)
        )
```

Pyodide 初始化一次，缓存在全局 `_sandbox_ctx` 中。每次执行创建新的 `pyodide.console.Console` 实例隔离作用域。

## Data Flow

```
User: "搜索GDP排名并计算平均值"
    │
    ▼
agent_node (JSON Mode)
    │ {actions:[search:GDP, search:平均收入]}
    ▼
tool_node (asyncio.gather)
    ├── search "GDP排名" → ToolResult(...)
    └── search "平均收入" → ToolResult(...)
    │ 合并 Observation
    ▼
agent_node → final_answer
    │
    ▼
chart_planner_node → answer_node
    │
    ▼
User sees: 文本 + 图表
```

## Error Handling

- **Schema 不完整** → 启动时 log warning，工具不被注册，不影响其他工具
- **并行中单个失败** → `return_exceptions=True`，成功的结果正常返回，失败的返回 error 结构
- **Pyodide sync timeout** → `concurrent.futures.TimeoutError` → 返回 `ToolResult.failure("TIMEOUT")`
- **JSON 解析失败** → agent_node fallback 到 `_force_final_answer`

## Testing Strategy

1. **单元测试 `ToolSchema`**：合法/非法 schema、缺少 required、未知类型
2. **单元测试 `ToolRegistry.discover()`**：mock `__subclasses__()` 返回带/不带 `_is_tool` 的类
3. **单元测试并行路径**：2 个成功、1成功1失败、超时、>3 限制
4. **集成测试 Pyodide**：简单代码执行、timeout、import pandas
5. **端到端**：完整三阶段流水线 + 新工具系统
