# AI Agent Platform Roadmap（V0.3 → V2.0）

> 项目目标：
>
> 从一个基础 AI Chat 系统，逐步演进为一个真正具备：
>
> - 多 Agent
> - Workflow
> - Tool Calling
> - Memory
> - Reflection
> - MCP
> - 企业级 Runtime
>
> 的 AI Agent Platform。

---

# 一、当前架构评估（V0.2）

当前项目已经具备：

```text
React Frontend
    ↓
SpringBoot BFF
    ↓
Python AI Service
    ↓
LangGraph
```

当前能力：

- SSE 流式输出
- Conversation 会话管理
- PostgreSQL 持久化记忆
- LangGraph 基础工作流
- 历史会话
- Markdown 渲染
- 基础工程化

当前阶段定位：

# AI Chat Runtime（基础版）

当前还不是真正的 Agent System。

下一阶段核心目标：

# 从 Chat 升级为 Agent Runtime

---

# 二、整体架构演进路线

# V0.2（当前）

```text
Chat System
```

核心：

- 单 Agent
- 单节点
- 基础上下文

---

# V0.3

```text
Tool Calling Runtime
```

核心：

- Tool Calling
- ReAct
- Agent Loop
- Tool Registry

---

# V0.4

```text
Router Agent System
```

核心：

- Router
- 多职责 Agent
- Agent Registry

---

# V0.5

```text
Planner + Executor Multi-Agent
```

核心：

- Task Planning
- Multi-Agent 协作
- Workflow

---

# V0.6

```text
Reflection System
```

核心：

- AI 自我检查
- Retry
- Self Correction

---

# V0.7

```text
Human In The Loop
```

核心：

- 审批流
- 人工确认
- 风险控制

---

# V1.0

```text
AI Agent Platform
```

核心：

- Agent Marketplace
- Tool Marketplace
- Long Memory
- Workspace

---

# V2.0

```text
Agent Operating System
```

核心：

- MCP
- A2A
- Multi Runtime
- Distributed Agent
- Autonomous Workflow

---

# 三、核心架构设计（最终形态）

```text
Frontend (React)
    ↓
SpringBoot Gateway/BFF
    ↓
AI Runtime Gateway
    ↓
LangGraph Runtime
    ↓
Agent System
    ↓
Tool Runtime / MCP / RAG
    ↓
Memory System
```

---

# 四、V0.3 规划（最关键阶段）

# 目标

让系统真正具备：

# Tool Calling 能力

这是 AI Agent 的第一道门槛。

---

# V0.3 要实现的能力

| 功能 | 优先级 | 必须实现 |
|---|---|---|
| Tool Calling | P0 | ✅ |
| Tool Registry | P0 | ✅ |
| ReAct Loop | P0 | ✅ |
| Search Tool | P0 | ✅ |
| Python Sandbox | P1 | ✅ |
| File Tool | P1 | ✅ |
| RAG 基础版 | P1 | ✅ |
| Tool UI 状态 | P1 | ✅ |
| Tool Streaming | P2 | 可选 |

---

# 1. Tool Registry（核心）

# 为什么必须做？

因为未来所有 Agent：

- Search
- Browser
- SQL
- GitHub
- Code
- File

都要统一管理。

如果不做 Registry：

后面一定失控。

---

# 推荐目录结构

```text
ai_service/
  tools/
    base.py
    registry.py

    search/
      tool.py

    python/
      tool.py

    file/
      tool.py
```

---

# Base Tool 设计

```python
class BaseTool:
    name: str
    description: str
    input_schema: dict

    async def execute(self, input):
        pass
```

---

# Registry

```python
tool_registry = {
    "search": SearchTool(),
    "python": PythonTool(),
}
```

---

# 学习重点

这一阶段你会理解：

- Tool 抽象
- Tool 生命周期
- Tool Schema
- Function Calling
- Tool 管理

---

# 2. ReAct Loop（非常重要）

# 目标

实现：

```text
Thought
Action
Observation
```

循环。

---

# LangGraph 结构

```text
User
  ↓
Agent
  ↓
Need Tool?
 ├── Yes → Tool Node
 └── No → Final
```

---

# 推荐节点

```text
router_node
agent_node
tool_node
final_node
```

---

# State 设计（重要）

```python
class AgentState(TypedDict):
    messages: list
    current_tool: str
    tool_result: str
    reasoning_steps: list
```

---

# 学习重点

你会真正理解：

# Agent Loop 是什么

这是 AI Agent 核心。

---

# 3. Search Tool

# 第一优先级 Tool

推荐：

- Tavily
- Serper
- DuckDuckGo

不要一开始自己爬虫。

---

# Search Tool 目标

支持：

```text
“帮我搜索 LangGraph 最新教程”
```

Agent 自动：

- 判断需要搜索
- 调用 Tool
- 获取结果
- 总结结果

---

# 4. Python Sandbox

# 目标

让 Agent：

- 执行 Python
- 数据分析
- 画图
- 算法计算

---

# 推荐方案

初期：

```text
Restricted Python Runtime
```

后期：

```text
Docker Sandbox
```

---

# 注意事项

一定要隔离：

- 文件系统
- 网络
- 系统命令

否则非常危险。

---

# 5. File Tool

# 目标

Agent 可以：

- 读取文件
- 分析代码
- 总结内容

---

# 推荐能力

支持：

- txt
- md
- pdf
- docx
- code files

---

# 6. RAG（基础版）

# 不要一开始做复杂 RAG

只做：

```text
上传文件
 → 向量化
 → 检索
 → 回答
```

即可。

---

# 推荐技术栈

| 模块 | 推荐 |
|---|---|
| Embedding | OpenAI / BGE |
| Vector DB | pgvector |
| Splitter | RecursiveTextSplitter |
| Retriever | LangChain Retriever |

---

# V0.3 前端升级

# 必须增加

---

# 1. Tool Call UI

例如：

```text
🔍 正在搜索...
🐍 正在执行 Python...
📄 正在读取文件...
```

---

# 2. Reasoning 展示

例如：

```text
AI 思考过程（可折叠）
```

---

# 3. 文件上传

必须支持：

- 拖拽上传
- 多文件
- 文件预览

---

# V0.3 后端（SpringBoot）升级

---

# 1. Tool Event Stream

SpringBoot 需要支持：

```text
tool_start
tool_result
reasoning
```

SSE 事件。

---

# 2. Conversation Runtime

后端不要只存消息。

开始存：

```json
{
  "conversationId": "",
  "currentAgent": "",
  "currentStep": "",
  "toolCalls": []
}
```

---

# V0.3 完成后你会真正学会

- ReAct
- Tool Calling
- LangGraph State
- Tool Runtime
- Agent Loop
- AI Workflow

---

# 五、V0.4 规划（真正进入 Agent）

# 目标

开始：

# 多职责 Agent

---

# 核心思想

# Agent ≠ AI

而是：

# 有职责的 Runtime Node

---

# V0.4 要实现

| 功能 | 必须 |
|---|---|
| Router Agent | ✅ |
| Agent Registry | ✅ |
| Dynamic Agent Switch | ✅ |
| Agent Prompt System | ✅ |
| Agent Memory | ✅ |

---

# Agent Registry

```yaml
agents:
  - name: coder
  - name: researcher
  - name: writer
```

---

# Router Agent

负责：

```text
判断问题属于哪个 Agent
```

---

# 示例

```text
代码问题 → coder
写作问题 → writer
搜索问题 → researcher
```

---

# LangGraph 结构

```text
Router
 ├── coder
 ├── writer
 └── researcher
```

---

# 学习重点

你会理解：

- 多 Agent
- Router
- Agent Isolation
- Prompt Engineering
- Context Isolation

---

# 六、V0.5 规划（真正的 Multi-Agent）

# 目标

开始：

# Planner + Executor

---

# 为什么重要？

因为复杂任务：

```text
无法一步完成
```

---

# 示例

用户：

```text
帮我分析一个 GitHub 项目
```

---

# Planner

拆任务：

```text
1. 获取仓库
2. 分析 README
3. 分析架构
4. 分析代码
5. 输出总结
```

---

# Executor

逐步执行。

---

# 需要实现

| 功能 | 必须 |
|---|---|
| Planner | ✅ |
| Task Queue | ✅ |
| Executor | ✅ |
| Workflow State | ✅ |
| Retry | ✅ |

---

# Workflow State

```python
class WorkflowState(TypedDict):
    tasks: list
    current_task: str
    completed_tasks: list
    failed_tasks: list
```

---

# 学习重点

你会真正理解：

- Workflow
- Planning
- Multi-Step Reasoning
- Task Orchestration

---

# 七、V0.6 规划（Reflection）

# 目标

让 AI：

# 检查自己

---

# 示例

```text
Coder Agent
  ↓
Reviewer Agent
  ↓
发现错误
  ↓
重新修复
```

---

# Reflection 非常关键

这是：

- Devin
- Manus
- OpenHands

核心能力。

---

# 需要实现

| 功能 | 必须 |
|---|---|
| Reviewer Agent | ✅ |
| Retry Loop | ✅ |
| Self Correction | ✅ |
| Score System | ✅ |

---

# 八、V0.7（Human In The Loop）

# 目标

高风险操作：

# 人工审批

---

# 示例

```text
AI 要删除数据库
```

系统：

```text
等待用户确认
```

---

# 必须实现

| 功能 | 必须 |
|---|---|
| Pause Workflow | ✅ |
| Resume Workflow | ✅ |
| Approval UI | ✅ |
| Risk Classification | ✅ |

---

# 九、V1.0（真正平台化）

# 目标

真正成为：

# AI Agent Platform

---

# 要实现

| 功能 | 必须 |
|---|---|
| Agent Marketplace | ✅ |
| Tool Marketplace | ✅ |
| Workspace | ✅ |
| Team Collaboration | ✅ |
| Long Memory | ✅ |
| Multi User | ✅ |

---

# 十、V2.0（Agent OS）

# 目标

进入：

# Agent Operating System

---

# 核心能力

| 功能 | 必须 |
|---|---|
| MCP | ✅ |
| A2A | ✅ |
| Distributed Agent | ✅ |
| Multi Runtime | ✅ |
| Autonomous Workflow | ✅ |

---

# 十一、数据库规划（建议）

# 当前

你只有：

```text
conversation
messages
```

---

# 未来必须增加

| 表 | 作用 |
|---|---|
| agent_definition | Agent 定义 |
| tool_definition | Tool 定义 |
| workflow_runtime | Workflow 状态 |
| task_runtime | Task 状态 |
| memory_records | Memory |
| tool_call_logs | Tool 调用记录 |
| reasoning_logs | 推理日志 |

---

# 十二、最推荐的目录结构（未来）

```text
ai_service/

  agents/
  workflows/
  tools/
  memory/
  runtime/
  prompts/
  rag/
  graph/
  schemas/
  checkpoints/
```

---

# 十三、你的真正学习路线

# 第一阶段

重点：

```text
Tool Calling
```

---

# 第二阶段

重点：

```text
Router + Agent
```

---

# 第三阶段

重点：

```text
Workflow + Planner
```

---

# 第四阶段

重点：

```text
Reflection + Memory
```

---

# 第五阶段

重点：

```text
MCP + Agent OS
```

---

# 十四、你未来真正会获得的能力

不是：

```text
“会 LangGraph API”
```

而是：

# AI Agent Architect

能力。

包括：

- Workflow
- Agent Runtime
- Memory System
- Tool Runtime
- Context Engineering
- AI Infra
- Multi-Agent Architecture

---

# 十五、当前最推荐你立刻开始做的事情

# 第一优先级

立即开始：

# V0.3 Tool Calling

不要急：

- MCP
- 多 Agent
- Reflection
- A2A

---

# 当前最佳学习模式

每天：

| 时间 | 内容 |
|---|---|
| 1 小时 | 学理论 |
| 2 小时 | 写代码 |

---

# 核心原则

```text
边做边学 > 纯教程
```

---

# 十六、最终目标

最终形成：

# 企业级 AI Agent Platform

而不是：

```text
“AI Chat Demo”
```

这是两条完全不同的路线。

