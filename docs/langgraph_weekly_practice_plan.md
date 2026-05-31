# LangGraph Weekly Practice Plan (V0.2 -> V0.3)

> 适用对象：LangGraph 初学者（当前项目为 V0.2，目标先完成 V0.3 P0）
>
> 使用方式：你每周按本计划完成任务，然后把产出贴给我，我会按同一周的验收标准带你复盘和补课。

## 0. 学习节奏与规则

- 每周建议投入：3-6 小时（最小 1 小时理论 + 2 小时实操）
- 学习原则：边做边学，先打通最小闭环，再追求完整度
- 每周固定输出四件事：
  1. 本周学习笔记
  2. 代码或设计改动
  3. 自测结果
  4. 下周风险清单

## 1. 当前项目基线（你现在在哪）

当前 `ai_service` 已具备：

- FastAPI + SSE 流式输出
- LangGraph 单节点工作流（`llm -> END`）
- PostgreSQL Checkpointer 记忆能力
- 会话历史读取接口

核心文件：

- `main.py`
- `graph/graph.py`
- `graph/nodes.py`
- `graph/state.py`
- `config.py`
- `ai_agent_platform_roadmap_v_0_to_v_2.md`

## 2. 8 周实操计划

### Week 1 - 读懂 V0.2 全链路

**学习目标**

- 理解请求从 API 入口进入 LangGraph 并以 SSE 返回的完整路径
- 理解 `thread_id` 与会话历史的关系

**动手任务**

- 阅读并标注：`main.py`、`graph/graph.py`、`graph/nodes.py`、`graph/state.py`
- 画一张执行流程图：`/api/v1/generate/stream -> graph -> on_chat_model_stream -> SSE`
- 运行并观察 mock/llm 两个分支

**验收标准**

- 能脱离代码口述完整执行链路（3-5 分钟）
- 能解释 `checkpointer` 在哪里初始化、在哪里被读取

**本周产出**

- `docs/week1_v0_2_flow_notes.md`（如果没有 docs 目录就新建）

---

### Week 2 - 设计 V0.3 State（为 Agent Loop 铺路）

**学习目标**

- 掌握 LangGraph State 设计方法
- 为 Tool Calling 预留状态字段

**动手任务**

- 基于 roadmap 设计 `AgentState v1`，至少包含：
  - `messages`
  - `current_tool`
  - `tool_result`
  - `reasoning_steps`
- 写清每个字段的写入节点、读取节点、生命周期

**验收标准**

- 能说明每个字段为什么存在，不是“为了以后可能用”
- 能说明字段冲突如何处理（覆盖/追加）

**本周产出**

- `docs/week2_state_design_v1.md`

---

### Week 3 - 搭建 Tool Registry 最小骨架（P0）

**学习目标**

- 理解 Tool 抽象与注册机制
- 为后续工具扩展建立统一入口

**动手任务**

- 设计目录（先建骨架，不追求功能完整）：

```text
tools/
  base.py
  registry.py
  search/
    tool.py
```

- 在 `base.py` 定义工具基础接口（name/description/input_schema/execute）
- 在 `registry.py` 支持注册、获取、列出工具

**验收标准**

- 新增工具时不需要改核心运行逻辑
- 能通过一个最小示例完成注册与调用

**本周产出**

- `docs/week3_tool_registry_design.md`

---

### Week 4 - 把图升级为 ReAct 结构（P0）

**学习目标**

- 理解 `Thought -> Action -> Observation -> Final` 的图映射
- 掌握条件路由与循环

**动手任务**

- 设计节点：`router_node`、`agent_node`、`tool_node`、`final_node`
- 设计分支：Need Tool? Yes -> `tool_node`; No -> `final_node`
- 定义每个节点输入输出（state 变化）

**验收标准**

- 能画出节点图并解释每条边触发条件
- 能说明如何防止无限循环（例如 max_steps）

**本周产出**

- `docs/week4_react_graph_design.md`

---

### Week 5 - 接入 Search Tool 并打通闭环（P0）

**学习目标**

- 完成一次真实工具调用闭环
- 理解工具结果如何回流到最终回答

**动手任务**

- 接入一个搜索工具（Tavily/Serper/DuckDuckGo 三选一）
- 在图中实现：判断需要搜索 -> 调用工具 -> 用工具结果回答
- 准备 5 条测试问题（至少 3 条应触发工具）

**验收标准**

- 搜索类问题稳定走工具分支
- 最终回答中能体现工具结果（不是忽略 tool_result）

**本周产出**

- `docs/week5_search_tool_e2e.md`

---

### Week 6 - 扩展 Python/File Tool 与安全边界（P1）

**学习目标**

- 理解高风险工具的边界与约束
- 建立统一错误处理模型

**动手任务**

- Python Tool：先做受限执行策略设计（禁系统命令/禁网络）
- File Tool：先支持 `txt`、`md`、`py` 三类
- 定义工具统一错误结构（code/message/retryable）

**验收标准**

- 能区分可恢复错误 vs 不可恢复错误
- 失败时系统可给出明确可读反馈

**本周产出**

- `docs/week6_tool_safety_and_error_model.md`

---

### Week 7 - 事件流协议升级（AI Service -> BFF -> Frontend）

**学习目标**

- 理解工具事件流在产品体验中的作用
- 建立可落地的事件协议

**动手任务**

- 设计并输出事件类型：`tool_start`、`tool_result`、`reasoning`
- 约定每类事件字段（conversationId/toolName/payload/timestamp）
- 与现有 token 流格式做兼容策略

**验收标准**

- 能描述前端如何消费每种事件
- 能描述 BFF 透传时不丢字段的约束

**本周产出**

- `docs/week7_event_stream_contract.md`

---

### Week 8 - RAG 基础版预研 + V0.3 收口

**学习目标**

- 形成最小 RAG 落地方案
- 完成 V0.3 阶段性复盘

**动手任务**

- 设计最小流程：上传 -> 切分 -> 向量化 -> 检索 -> 回答
- 给出技术选型草案：Embedding + pgvector + Retriever
- 汇总 V0.3 P0/P1 完成度与遗留问题

**验收标准**

- 有清晰 backlog（P0 已闭环，P1 有排期）
- 能给出下一阶段 V0.4 的进入条件

**本周产出**

- `docs/week8_rag_plan_and_v0_3_review.md`

## 3. 每周复盘模板（你每周发我这 5 项）

```markdown
# Week X 复盘

## 1) 我完成了什么
- 

## 2) 我卡住的点
- 

## 3) 本周代码/设计改动
- 

## 4) 自测结果
- 

## 5) 下周计划
- 
```

## 4. 和我配合的方式（建议）

每周你只要给我一句：

- `开始 Week X`（我会先讲本周目标与关键概念）
- `验收 Week X`（我会按验收标准逐项检查）
- `补课 Week X`（我会针对你卡点做小练习）

---


