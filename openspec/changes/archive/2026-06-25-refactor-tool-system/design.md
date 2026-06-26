## Context

当前工具系统架构：`BaseTool` (ABC) → 具体 Tool 类 → `main.py` 手动注册到 `ToolRegistry` → `agent_node` 硬编码 prompt 描述工具。添加一个工具需改动 3 个文件，工具结果格式不统一。ReAct 循环单次只能调用一个工具。

## Goals / Non-Goals

**Goals:**
- 工具插件式注册：创建单个文件即完成工具接入，自动发现 + 自动注册
- 统一工具定义格式（OpenAI function schema），自动生成 LLM 工具描述
- Python 代码执行沙箱，支持数据分析类工具调用
- 单次 ReAct 迭代可并行调用多个独立工具

**Non-Goals:**
- 不做可视化工具编排界面
- 不添加具体业务工具（数据库查询、文件上传等）
- 不做多 Agent 协作

## Decisions

### 1. 工具注册：文件约定自动发现 + 装饰器注册

**方案**：每个工具文件放置在 `tools/` 目录下，工具类使用 `@tool` 装饰器标记，`ToolRegistry` 在启动时扫描 `tools/` 目录自动发现并注册。

```python
# tools/search/tool.py
from tools.base import tool, BaseTool, ToolSchema

@tool
class SearchTool(BaseTool):
    name = "search"
    description = "Web search via Tavily API"
    schema = ToolSchema(
        parameters={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            }
        }
    )

    async def execute(self, input: dict) -> ToolResult:
        ...
```

**替代方案**：
- 配置注册（YAML/JSON）：更灵活但增加维护负担
- 手工注册（当前方案）：简单但不可扩展

**选择理由**：装饰器方案改动最小，符合 Python 惯例，`main.py` 无需修改。

### 2. 工具 Schema 标准化：OpenAI function schema

**方案**：`BaseTool` 新增 `schema: ToolSchema` 字段，使用 OpenAI function/tool 定义格式。`agent_node` 从 `ToolRegistry.list_tools()` 获取 schema 列表，注入到 JSON Mode prompt 中。

```python
class ToolSchema(BaseModel):
    parameters: dict  # JSON Schema for tool input

class BaseTool(ABC):
    name: str
    description: str
    schema: ToolSchema

    @abstractmethod
    async def execute(self, input: dict) -> ToolResult: ...
```

**选择理由**：OpenAI function schema 是最广泛使用的工具定义标准，DeepSeek/Claude/GPT 均兼容，未来迁移到 native function calling 时无需改写。

### 3. 并行工具调用协议

**方案**：`agent_node` JSON 输出从单工具格式升级为支持多工具：

```json
// 当前
{"action":"tool","tool":"search","query":"..."}

// 新：单工具（兼容）
{"action":"tool","tool":"search","query":"..."}

// 新：并行多工具
{
  "actions": [
    {"tool":"search","query":"2024 GDP排名"},
    {"tool":"search","query":"2024 出生率"}
  ]
}
```

`tool_node` 检测 `actions` 数组时并行执行，`route` 返回到 `agent`。

**LangGraph 实现**：不引入 Send API（避免复杂度），在 `tool_node` 内部使用 `asyncio.gather()` 并行执行。需保证工具间无依赖（当前所有工具均独立）。

### 4. 代码沙箱：Docker 容器执行

**方案**：方案对比：

| 方案 | 安全性 | 延迟 | 维护成本 | 选择 |
|------|--------|------|----------|------|
| Docker 容器 | 高 | 中(冷启动~2s) | 中 | ✅ 选择 |
| Pyodide (WASM) | 高 | 低(~200ms) | 低 | 备选 |
| e2b.dev | 高 | 低 | 低(外部服务) | 过度 |
| subprocess | 低 | 极低 | 低 | 不安全 |

选择 Docker：当前部署已用 Docker，新增一个 sandbox 容器成本低。支持 pip 包安装、文件挂载、CPU/内存限制、超时终止。

```python
@tool
class CodeSandboxTool(BaseTool):
    name = "execute_python"
    description = "Execute Python code in a sandboxed environment"
    schema = ToolSchema(parameters={
        "type": "object",
        "required": ["code"],
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
            "timeout": {"type": "integer", "default": 30}
        }
    })

    async def execute(self, input: dict) -> ToolResult:
        # Run in Docker container with resource limits
        ...
```

**回退方案**：如果 Docker 沙箱部署复杂，降级为 Pyodide（pip install pyodide，纯 Python WASM 运行时）。

## Risks / Trade-offs

- [风险] 自动发现扫描 `tools/` 目录可能在大型项目中缓慢 → 仅在启动时执行一次，结果缓存
- [风险] 并行工具执行导致 LLM token 消耗增加（多个结果同时返回）→ agent_node 内限制最多 3 个并行工具
- [风险] Docker 沙箱冷启动延迟影响用户体验 → 预启动 warm container pool，或降级 Pyodide
- [取舍] 放弃原生 Function Calling（用户明确要求），继续使用 JSON Mode → 需要更严格的 prompt 工程确保 `actions` 数组格式正确
