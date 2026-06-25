你现在需要对一个现有 AI Agent 项目进行架构重构，目标是升级为更标准的生产级 AI Agent Graph（类似 LangGraph / Codex / Claude Code 架构）。

当前版本：V0.4（三阶段 pipeline）
目标版本：V1（模块化 + 可扩展 + 工程化）

========================
🎯 重构目标
========================

请在不改变现有业务能力的前提下，重构 agent graph，使其具备以下能力：

1. 更清晰的职责拆分（避免 agent 过载）
2. 支持可插拔工具系统（tools registry）
3. chart 生成独立为结构化 pipeline
4. answer 输出支持 streaming + markdown + chart embedding
5. 支持 planner-first 架构（减少 agent 乱调用工具）
6. 支持 future extension（RAG / memory / browser / code executor）

========================
🏗 当前架构问题（需要解决）
========================

当前结构：

agent → tool → agent → chart_planner → answer

问题包括：
- agent 同时负责：推理 + tool calling + 判断流程（职责过重）
- chart_planner 是“后置”，导致信息不足
- tool routing 过于依赖 agent decision
- answer node 只是 formatter，没有 planning
- 无统一 planner 层
- 状态结构不清晰（state污染风险）

========================
🚀 目标架构（必须实现）
========================

请重构为以下 5 层 Graph：

(1) Planner Node（新增）
--------------------------------
输入：用户问题 + history
输出：
- task plan（steps）
- 是否需要 tools
- 是否需要 charts
- 是否需要 retrieval

作用：
👉 统一决策，不再让 agent 乱做规划

------------------------

(2) Executor Node（原 agent）
--------------------------------
职责：
- 执行 planner 的 step
- 调用 tools（通过 tool router）
- 只做“执行”，不做规划

必须改造：
- 移除自由式 ReAct
- 改为 structured execution

------------------------

(3) Tool Router Node（增强）
--------------------------------
职责：
- 统一工具调用入口
- 支持 registry tools
- tool input/output 标准化

要求：
- tools 必须注册式管理
- 禁止 agent 直接调用 tool

------------------------

(4) Chart Pipeline Node（重构）
--------------------------------
替换当前 chart_planner

改为：

Chart Extractor →
Chart Builder →
Chart Validator

输入：
- executor outputs + state

输出：
- structured chart spec list

必须支持：
- 多图
- 图类型识别（line/bar/pie/scatter）
- 数据标准化

------------------------

(5) Answer Renderer Node（升级）
--------------------------------
职责：
- streaming 输出
- 插入 [CHART:x] 占位符
- markdown formatting
- 结构化输出整合

要求：
- answer 不允许再调用 tools
- answer 只负责表达

========================
🧠 State 结构重构（必须做）
========================

请设计新的 State：

必须包含：

- messages
- plan
- steps
- tool_calls
- tool_results
- charts (structured)
- final_context
- execution_trace

要求：
👉 state 必须避免字段污染
👉 tool output 与 chart output 分离

========================
🔁 Graph Flow（必须实现）

START
↓
Planner
↓
Executor
↓
Tool Router (loop if needed)
↓
Executor (loop until done)
↓
Chart Pipeline
↓
Answer Renderer
↓
END

========================
⚙️ 工程化要求
========================

请同时优化以下内容：

1. tool system 改为 registry 模式
2. node 输入输出必须 typed（建议 dataclass / pydantic）
3. routing functions 必须纯函数化
4. 所有 node 必须无副作用（只修改 state copy）
5. 支持 future streaming execution（graph.stream）

========================
📊 Chart 系统升级要求
========================

必须支持：

- line chart（趋势）
- bar chart（对比）
- pie chart（占比）
- scatter（关系）
- multi-series chart

chart spec 示例：

{
"type": "line",
"title": "...",
"x": [...],
"y": [...],
"series": [...]
}

并且必须支持：

- 自动数据清洗
- 单位统一
- 缺失值处理

========================
🧩 可扩展能力（预留接口）
========================

请预留：

- RAG retriever node
- memory node
- browser node
- code executor node
- sql query node

========================
🚫 禁止行为
========================

- 禁止 agent 再做 chart planning
- 禁止 tool 直接返回未结构化数据
- 禁止 answer node 做逻辑推理
- 禁止 graph 变成“线性链式调用”

========================
🎯 输出要求
========================

请输出：

1. 新 graph 结构代码（LangGraph）
2. state 定义
3. 每个 node 设计
4. routing functions
5. tool registry 设计
6. chart pipeline 设计

重点：保持工程可读性 + 可扩展性 + 清晰职责边界