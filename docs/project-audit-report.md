# AI Agent 项目架构审计报告

**日期**: 2026-06-27  
**分支**: feature/20260627/unify-chart-pipeline

---

## 一、整体架构

```
React (localhost:3000)
  │ POST /api/chat/stream (SSE)
  ▼
Spring Boot (WebFlux Gateway)
  │ 鉴权 + 透传 POST /api/v1/generate/stream
  ▼
Python AI Service (FastAPI + LangGraph)
  │
  ├── stream_generate() — SSE 入口
  │   ├── RouterAgent → 关键词/LLM 匹配 Agent
  │   ├── AgentFactory → 构建 AgentRuntime
  │   ├── CollaborationEngine → 顺序/并行/监督执行
  │   ├── multi_agent_graph → LangGraph 状态图
  │   └── StreamingEventBus → 实时 SSE 进度事件
  │
  ├── Tools: search(browser/tavily), execute_python, browser, time
  └── DB: PostgreSQL (agent_definitions, chat_messages)
```

### 目录结构

```
ai_service/
├── api/routes/chat.py          # SSE 流式入口 (555行)
├── core/
│   ├── collaboration.py        # Agent 协作引擎 (350行)
│   ├── router_agent.py         # Agent 路由器
│   ├── agent_factory.py        # Agent 实例工厂
│   └── streaming_event_bus.py  # 事件总线
├── graph/
│   ├── nodes.py                # LangGraph 节点 (agent/tool/chart_planner/answer)
│   ├── multi_agent_graph.py    # 多 Agent 图 (router→collab→merge→END)
│   └── state.py                # 图状态定义
├── tools/sandbox/tool.py       # execute_python 工具
├── tools/search/tool.py        # Tavily 搜索工具
├── chart/                      # ⚠️ 新图表模块（已创建但未接入主流程）
│   ├── chart_service.py        # 从未被 import
│   ├── chart_theme.py          # 仅在子进程 preamble 中间接使用
│   └── renderers/matplotlib_renderer.py  # 从未被 import
├── services/minio_client.py    # MinIO 图片上传
├── charts/                     # ⚠️ 旧 ECharts 图表类型（遗留代码）
└── db/migrations/              # 数据库迁移
```

---

## 二、图表生成全链路分析

### 当前唯一路径

```
用户请求(含"图表/折线图/柱状图")
  │
  ▼
RouterAgent (触发词匹配 → 选中 agents)
  │
  ▼
CollaborationEngine._sequential()
  │  遍历 agents:
  │    _run_agent_with_tools(runtime, context)
  │      ├── LLM 决策 → 调用 search / execute_python
  │      ├── execute_python 执行 → 子进程
  │      │   ├── preamble: SSL禁用 + ChartTheme + 资源限制
  │      │   ├── 执行LLM生成的Python代码
  │      │   ├── 扫描 stdout + CWD 找 .png
  │      │   └── 上传 MinIO → 返回 URL
  │      └── LLM 最终回答
  │
  ▼
merge_node → collab_result 放入 state
  │
  ▼
chat.py: 从 final_state 逐字符流式输出 collab_result
  │
  ▼
image.uploaded SSE 事件 → 前端 addImage → <img src=url>
```

---

## 三、根因分析

### 根因 1：LLM 不调用 execute_python（核心问题）

**症状**: 收到图表请求后只调用 search，不调用 execute_python。

**根因**: 
- DeepSeek v4-flash 模型倾向于只用 search 获取信息后直接文本回答
- Agent 同时有 search + execute_python 时，LLM 走捷径只做搜索
- Prompt 写了 MANDATORY 但 LLM 不完全遵守

**证据**: 多次 SSE 日志显示 agent 只调用了 search

### 根因 2：图片扫描路径不完整

```python
# sandbox/tool.py — 只扫描 CWD
for f in _os_module.listdir(cwd):  # cwd = ai_service/
```

如果 LLM 代码用绝对路径 `plt.savefig("/tmp/chart.png")`，文件在 `/tmp`，扫描不到。

### 根因 3：ChartService 模块死代码

`chart/` 模块（ChartService/ChartTheme/MatplotlibRenderer）已创建但**从未被主流程调用**：
- `chart_service.py` — 0 次 import
- `matplotlib_renderer.py` — 0 次 import
- `chart_theme.py` — 仅通过子进程 preamble `from chart.chart_theme import ChartTheme` 间接使用

### 根因 4：Agent 工具配置矛盾

| Agent | Tools | 问题 |
|-------|-------|------|
| data_analyst | execute_python + search | LLM选search不走execute_python |
| general | search+execute_python+browser | 工具太多LLM难以选择 |
| code_analyst | execute_python | ✅ 只有execute_python，最可靠 |

### 根因 5：chat.py 代码质量问题

- 重复 import：`get_checkpointer` 导入了两次（第21行和第60行）
- 多行未使用的import：envelope_chart、envelope_token、emit_chart_envelopes等
- 调试日志未清理
- `_sanitize_delta()` 函数重复定义 import re

### 根因 6：旧 charts/ 目录残留

```python
charts/types/{area,bar,line,pie,radar,scatter}.py
```
ECharts 时代的遗留代码，不再被调用但仍在代码库中。

---

## 四、修复方案

### 关键修复（解决图表不生成）

| # | 方案 | 原理 |
|---|------|------|
| 1 | data_analyst 只保留 execute_python 工具 | 强制 LLM 必须用 execute_python |
| 2 | preamble 自动追加 savefig | 兜底：即使 LLM 忘记 savefig 也能出图 |
| 3 | 扫描 /tmp 下的 PNG | 覆盖 LLM 使用绝对路径的情况 |

### 架构清理

| # | 方案 |
|---|------|
| 4 | 删除 charts/ 目录（旧 ECharts 遗留） |
| 5 | chat.py 去重 import，删除未使用的 import |
| 6 | 删除 chart/chart_service.py 等死代码或接入主流程 |
