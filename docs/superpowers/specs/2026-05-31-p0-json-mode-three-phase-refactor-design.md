# ReAct Agent P0 重构设计：JSON Mode + 三阶段流水线 + 图表后处理

**日期**: 2026-05-31
**状态**: 已确认
**目标**: 解决图表生成不稳定、文本解析 JSON 脆弱、流式架构过度复杂三大核心问题

---

## 一、目标

1. 所有结构化输出（工具调用、图表规划）使用 JSON Mode，从源头消除手动 JSON 解析
2. 图表生成从 ReAct 循环中分离为独立后处理步骤
3. 最终答案在 Normal Mode 下流式输出，通过 `[CHART:n]` 标记实现文本与图表动态穿插
4. 简化 SSE 流式协议和前端状态管理

---

## 二、约束

- 模型：DeepSeek v4-flash
- 不使用原生 Function Calling，使用 JSON Mode（`response_format: {"type": "json_object"}`）
- 保留 ReAct 循环的核心结构（agent_node → tool_node 迭代）
- 保留 search、browser、time 三个工具
- 保留 ECharts 前端渲染
- 保留 PostgreSQL LangGraph checkpoint

---

## 三、架构变更

```
当前架构（单循环，文本中解析 JSON）：
  User → agent_node ←→ tool_node → chart_node → END
           ↑ 手动 JSON 解析 + 多层补丁      ↑ pass-through

新架构（三阶段流水线）：
  
  阶段一：JSON Mode ReAct
    agent_node ←→ tool_node (search/browser/time)
    每次 LLM 输出：
      {"action":"tool","tool":"search","query":"..."}
      {"action":"final_answer"}
  
  阶段二：JSON Mode 图表规划
    独立 LLM 调用，从对话历史提取数据生成图表
    输出：{"charts": [{id,chart_type,title,data,...}]}
    SSE：立即发送 chart_ready 事件到前端
  
  阶段三：Normal Mode 流式最终答案
    LLM 自由流式输出带 [CHART:n] 标记的文本
    SSE：token 事件流 + 遇到标记触发图表渲染
    文本和图表动态穿插
```

### Graph 结构变更

```
START
  ↓
agent_node (JSON Mode)
  ├── action=="tool" → tool_node → agent_node (循环)
  └── action=="final_answer" → chart_planner_node (JSON Mode)
                                  ↓
                              answer_node (Normal Mode, streaming)
                                  ↓
                                END
```

---

## 四、阶段一：JSON Mode ReAct 数据收集

### 4.1 Agent Node

**System Prompt 核心部分**：

```
You are a ReAct agent. Your response MUST be valid JSON.

Tool call format:
{"action":"tool","tool":"<name>","query":"<query>"}

Final answer ready:
{"action":"final_answer"}

Available tools:
- search: web search. Use to find information.
- browser: open a URL. MUST use exact URL from search results.
- time: current date/time with optional timezone.

Rules:
1. Output ONLY the JSON. No other text, no markdown wrapping.
2. After search results, use browser to read at least one page before concluding.
3. After 1 browser failure, use search snippets directly.
4. Call final_answer when you have sufficient information.
Current server time: <datetime>
```

**代码简化**：删除以下函数/逻辑
- `_parse_tool_call()` — 70 行大括号匹配 JSON 搜索
- `_strip_thought_tags()` — [Thought] 标签过滤
- `_extract_tool_from_parsed()` — 多格式 JSON 兼容解析
- `_filter_chart_denial()` — 图表拒绝文本过滤（图表已移到阶段二）
- Time 重复防护中的关键词匹配（`"新闻", "天气", "today"`）
- 连续文本响应计数（JSON Mode 下不存在此情况）

替换为：
```python
# 核心逻辑
response = await llm.ainvoke(messages)  # llm 配置了 response_format
parsed = json.loads(response.content)
action = parsed.get("action")

if action == "tool":
    return {"current_tool": parsed["tool"], "tool_input": {"query": parsed["query"]}}
if action == "final_answer":
    return {"route": "chart_planner"}
```

**Guardrails 保留**：
- 最大迭代次数（20，来自环境变量）
- 重复工具调用检测（tool_name + normalized_query 精确匹配）
- 最大连续搜索次数（10，来自环境变量）

**Guardrails 移除**：
- Time 工具重复调用自动切换逻辑
- 连续文本响应计数

### 4.2 Tool Node

逻辑基本不变。移除 `generate_chart` 和 `output_text` 工具的 inline block 处理（不再需要 `pending_chart_spec`, `pending_text_block`）。

### 4.3 LLM 配置

```python
ChatOpenAI(
    model=settings.model,
    temperature=0.3,  # 低温度提高 JSON 格式稳定性
    api_key=settings.api_key,
    base_url=settings.base_url,
    response_format={"type": "json_object"},
    # 不再需要 extra_body={"thinking": {"type": "disabled"}}
)
```

---

## 五、阶段二：JSON Mode 图表规划

### 5.1 Chart Planner Node

ReAct 循环结束后调用，独立于文本生成。

```python
CHART_PLANNER_SYSTEM_PROMPT = """You are a data analyst. Analyze the conversation and extract 
chart-worthy data. Output valid JSON only.

{
  "charts": [
    {
      "id": 0,
      "chart_type": "bar",
      "title": "2024 Global GDP Rankings",
      "description": "Top 10 countries by GDP",
      "x_axis_label": "Country",
      "y_axis_label": "GDP (Trillion USD)",
      "data": [
        {"name": "USA", "value": 28.78},
        {"name": "China", "value": 18.53}
      ]
    }
  ]
}

Rules:
- chart_type: line | bar | pie | scatter | area | radar
- id: sequential integer starting from 0
- data: max 20 points
- pie charts: no x_axis_label/y_axis_label, use "name" and "value" only
- No numerical data → {"charts": []}
- Extract values from search/browser results accurately
- Do NOT fabricate or estimate data not found in the conversation
"""

async def chart_planner_node(state: State) -> dict:
    # 构建包含完整对话历史的 messages
    chart_messages = [
        SystemMessage(content=CHART_PLANNER_SYSTEM_PROMPT),
        *state["messages"],  # 用户问题 + ReAct 对话历史
    ]
    
    llm = ChatOpenAI(
        model=settings.model,
        temperature=0.1,  # 极低温度，数据提取要求精确
        response_format={"type": "json_object"},
        api_key=settings.api_key,
        base_url=settings.base_url,
    )
    
    response = await llm.ainvoke(chart_messages)
    result = json.loads(response.content)
    
    charts = result.get("charts", [])
    validated_charts = validate_chart_specs(charts)
    
    return {
        "chart_specs": validated_charts,
        "route": "answer",
    }
```

### 5.2 Chart Spec 验证

```python
def validate_chart_specs(charts: list) -> list[ChartSpec]:
    """验证并清理 LLM 输出的图表数据"""
    valid = []
    for c in charts:
        try:
            spec = ChartSpec(
                id=int(c.get("id", 0)),
                title=str(c.get("title", ""))[:200],
                chart_type=_validate_chart_type(c.get("chart_type", "bar")),
                description=str(c.get("description", ""))[:500],
                x_axis_label=str(c.get("x_axis_label", ""))[:100],
                y_axis_label=str(c.get("y_axis_label", ""))[:100],
                data=_validate_data_points(c.get("data", [])),
            )
            if spec.data:  # 只要有至少一个数据点就有效
                valid.append(spec.to_dict())
        except Exception as e:
            logger.warning(f"Chart validation failed: {e}")
    return valid

ALLOWED_CHART_TYPES = {"line", "bar", "pie", "scatter", "area", "radar"}

def _validate_chart_type(ct: str) -> str:
    ct = str(ct).strip().lower()
    return ct if ct in ALLOWED_CHART_TYPES else "bar"

def _validate_data_points(data: list) -> list[ChartDataPoint]:
    result = []
    for i, d in enumerate(data[:20]):  # 最多 20 个
        if not isinstance(d, dict):
            continue
        name = str(d.get("name", "")).strip()
        if not name:
            continue
        try:
            value = float(d.get("value", 0))
        except (ValueError, TypeError):
            continue
        group = str(d.get("group", "")).strip()
        result.append(ChartDataPoint(name=name, value=value, group=group))
    return result
```

### 5.3 ChartTool 废弃

`tools/chart/tool.py` 中 `ChartTool` 类不再在 ReAct 循环中注册或调用。文件可保留供将来使用，但不参与新的 Agent Graph。

---

## 六、阶段三：Normal Mode 流式最终答案

### 6.1 Answer Node

```python
ANSWER_SYSTEM_PROMPT_TEMPLATE = """You are a helpful AI assistant. Answer the user's question 
based on the research results. Use Markdown for formatting.

[Available Charts]
{chart_descriptions}

[Output Instructions]
- When discussing relevant data, reference charts using [CHART:n] on its own line
- Each chart MUST be referenced at least once
- Do NOT repeat chart data values as text — trust the chart to show them
- Write naturally, as if the chart is an integral part of your analysis
- Keep answers concise and well-structured

Current time: {now_str}
"""

async def answer_node(state: State) -> dict:
    chart_specs = state.get("chart_specs", [])
    
    # 构建图表描述
    chart_descriptions = "\n".join([
        f"Chart {c.get('id', i)} ({c.get('chart_type', 'bar')}): \"{c.get('title', '')}\" - "
        f"Shows {c.get('description', 'chart data')}"
        f" (x: {c.get('x_axis_label', 'N/A')}, y: {c.get('y_axis_label', 'N/A')})"
        for i, c in enumerate(chart_specs)
    ]) if chart_specs else "No charts available for this answer."
    
    system_content = ANSWER_SYSTEM_PROMPT_TEMPLATE.format(
        chart_descriptions=chart_descriptions,
        now_str=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    
    messages = [SystemMessage(content=system_content)] + list(state["messages"])
    
    llm = ChatOpenAI(
        model=settings.model,
        temperature=settings.temperature,
        streaming=True,  # Normal Mode, 流式
        api_key=settings.api_key,
        base_url=settings.base_url,
    )
    
    response = await llm.ainvoke(messages)
    
    return {
        "messages": [response],
        "chart_specs": chart_specs,
    }
```

### 6.2 SSE 流式处理

在 chat route 中：

```
graph.astream_events():
  
  阶段一（ReAct）：
    - agent_node 完成后 → 不产生 token 事件（JSON 被完全消费）
    - tool_node 执行时 → 发送 tool_start / tool_result 事件
  
  阶段二（图表规划）：
    - chart_planner_node 完成后 → 对每个 chart 发送 chart_ready 事件
    - 前端预加载图表数据
  
  阶段三（流式答案）：
    - answer_node streaming chunk → token 事件流
    - route 层检测 token 内容中的 [CHART:n]
    - 遇到标记时发送 chart 事件（触发前端渲染）
    - 后续 token 继续流式传输
```

### 6.3 前端 SSE 事件类型精简

```
精简后（7 种）:
  token              — 答案文本流（包含 [CHART:n] 标记）
  thought            — 思考过程（兼容保留）
  tool_start         — 工具开始执行
  tool_result        — 工具执行完成
  tool_summary       — 最终工具步骤汇总
  chart              — 图表数据（阶段二已发送，阶段三标记触发渲染）
  error              — 错误

移除的 6 种:
  block_start/block_chunk/block_end  — token 直出，不需 block 协议
  chart_placeholder/chart_ready      — 合并为 chart（预发送+标记触发）
  agent_step                         — 合入 tool_result 的 guard 字段
```

---

## 七、前端变更

### 7.1 useChat.ts 简化

```typescript
// 新 handleParsedEvent 简化版
const handleParsedEvent = (parsed: StreamPayload) => {
  const { type, payload } = parsed;
  
  switch (type) {
    case 'token':
      // 检查 [CHART:n] 标记
      const parts = splitChartMarkers(payload.content);
      for (const part of parts) {
        if (part.type === 'text') {
          appendText(part.content);
        } else if (part.type === 'chart') {
          // 触发图表渲染（数据已在阶段二预加载）
          renderChart(part.chartIndex);
        }
      }
      break;
    
    case 'chart':
      // 阶段二发送的图表数据，缓存起来
      chartDataCache.set(payload.id, payload.chartSpec);
      break;
    
    case 'tool_start':
      addThinkingStep({ tool: payload.toolName, status: 'running' });
      break;
    
    case 'tool_result':
      updateThinkingStep(payload.toolName, { 
        status: payload.status, 
        summary: payload.summary 
      });
      break;
    
    case 'tool_summary':
      finalizeThinkingSteps(payload.steps);
      break;
    
    case 'thought':
      // 兼容保留
      break;
    
    case 'error':
      handleError(payload.error);
      break;
  }
};
```

### 7.2 ChartRenderer 不变

`ChartRenderer.tsx` 使用 ECharts 渲染，chart_spec 数据格式不变，无需改动。

---

## 八、文件变更清单

### 删除的文件
- `ai_service/tools/chart/tool.py` — ChartTool 不再需要
- `ai_service/graph/chart_planner.py` — 旧图表规划器（未使用）
- `ai_service/graph/chart_generator.py` — 旧图表生成器（未使用）
- `ai_service/graph/content_composer.py` — 旧内容编排器（未使用）
- `ai_service/tools/output_text/tool.py` — OutputTextTool 不再需要

### 重写的文件
- `ai_service/graph/nodes.py` — agent_node、tool_node 重写，新增 chart_planner_node、answer_node，删除 llm_node
- `ai_service/api/events/event_mapper.py` — 简化 JSON 过滤逻辑，移除 _filter_chart_denial
- `ai_service/api/routes/chat.py` — 简化流式处理，移除 control_json_buffer/preamble_buffer
- `frontend/src/hooks/useChat.ts` — 简化事件处理，添加 [CHART:n] 标记解析

### 新增的文件
- `ai_service/graph/validators.py` — ChartSpec 验证逻辑

### 修改的文件
- `ai_service/graph/graph.py` — 新增 chart_planner 和 answer 节点
- `ai_service/graph/state.py` — 添加 route 字段
- `ai_service/domain/event_envelope.py` — 移除 chart_placeholder/chart_ready/block 相关函数
- `ai_service/tools/registry.py` — 移除 ChartTool 和 OutputTextTool 注册
- `ai_service/main.py` — 移除 ChartTool 和 OutputTextTool 注册
- `frontend/src/types/chat.ts` — 移除 block/chart_placeholder/chart_ready 类型
- `frontend/src/components/ChatMessage.tsx` — 移除 block 解析逻辑

### 不修改的文件
- `frontend/src/components/ChartRenderer.tsx` — 数据格式不变
- `backend/` — 全部不改
- `ai_service/tools/search/`, `browser/`, `time/` — 全部不改

---

## 九、测试计划

1. **JSON 解析确定性测试**：验证 JSON Mode 输出 100% 可解析
2. **图表验证器单元测试**：边界数据（空、超量、非法类型、0值）
3. **[CHART:n] 标记解析测试**：单图表、多图表、无图表、标记在开头/结尾/中间
4. **ReAct 循环收敛测试**：duplicate 检测、max iterations 触发
5. **SSE 事件顺序测试**：tool_start → tool_result → tool_summary → chart → token
6. **前端集成测试**：图表缓存放后再用标记触发渲染的时序

---

## 十、风险与对策

| 风险 | 对策 |
|------|------|
| DeepSeek JSON Mode 偶尔输出非法 JSON | `json.loads()` 外部包 try-catch，失败时重试一次（带更强的格式指令） |
| LLM 忘记插入 [CHART:n] 标记 | Prompt 中强调"每个图表至少引用一次" |
| LLM 虚构不存在的图表标记 | 前端遇到未知 chart_id 时忽略，不报错 |
| ReAct 阶段 JSON Mode 降低推理质量 | temperature 0.3（不是 0.1），保留一定创造性 |
| 图表规划阶段遗漏数据 | 在 answer prompt 中同时传入原始数据，LLM 可补充说明 |
