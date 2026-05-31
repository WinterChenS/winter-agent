# Winter Agent 深度分析与整改方案

## 一、架构总览

```
Frontend (React) → Backend (Spring Boot BFF) → AI Service (FastAPI + LangGraph)
    SSE/fetch          WebClient proxy              ReAct Loop + Tools
```

当前是一个 ReAct 模式的 AI Agent，支持搜索、浏览器、图表生成等工具调用。核心问题在于：**文本解析式工具调用** 是整个系统不稳定的根源。

---

## 二、核心问题诊断

### 问题 1：没有使用原生 Function Calling（★★★★★ 致命）

**现状**：LLM 在文本回复中输出 JSON，系统用 `_parse_tool_call()` 手动解析。

```python
# nodes.py:119 - 手动 JSON 搜索
def _parse_tool_call(content: str) -> tuple[str, str] | None:
    # 用大括号计数在文本中搜索 JSON 对象
    depth = 0
    start = -1
    for i, ch in enumerate(content):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        ...
```

**导致的问题**：
- LLM 经常在 JSON 前加前言（"Let me search that..."），需要 preamble buffer 缓冲 300 字符才能判断
- JSON 格式错误（缺少引号、多余逗号）直接导致工具调用失败
- 嵌套 JSON 或转义引号会破坏大括号计数
- 需要 `_strip_thought_tags()` 过滤 `[Thought]` 标签
- 需要 `_filter_chart_denial()` 过滤 "我无法生成图表" 文本
- 需要 `process_stream_token_event()` 整条流水线来过滤控制 JSON
- `control_json_buffer` 机制在流式场景下逐字符拼接 JSON，效率低且易出错

**影响范围**：
- `nodes.py`: `_parse_tool_call()`, `_strip_thought_tags()`, `_extract_tool_from_parsed()`
- `event_mapper.py`: `process_stream_token_event()`, `_filter_chart_denial()`, `is_tool_action_json()`
- `chat.py`: `collecting_control_json`, `control_json_buffer`, `preamble_buffer` 状态管理

### 问题 2：图表生成不稳定（★★★★★ 致命）

**现状**：图表通过 `generate_chart` 工具生成，但整个链路充满补丁。

```
LLM 文本输出 → _parse_tool_call 解析 → ChartTool.execute() → SSE 发往前端
     ↑                                                              ↓
  _filter_chart_denial()  ←──  LLM 经常输出"我无法生成图表"  ←──  前端渲染
```

**具体问题**：

| 环节 | 问题 | 位置 |
|------|------|------|
| 工具调用 | LLM 使用 pipe 格式 `"bar\|Title\|name:value"` ，逗号/冒号在数据中会破坏解析 | `chart/tool.py:69-89` |
| 工具调用 | LLM 有时输出图表描述文本而不是调用工具 | `event_mapper.py:24-43` |
| 结果过滤 | `_filter_chart_denial()` 用正则删除 "抱歉，我无法生成图表"，但这是事后补救 | `event_mapper.py:24-43` |
| 提示词 | System prompt 写 "NEVER say you cannot" 但 LLM 仍然拒绝 | `nodes.py:52` |
| 前端渲染 | `chart_placeholder` + `chart_ready` 两步协议，如果 ready 没到，骨架永远显示 | `useChat.ts:219-234` |
| 数据验证 | ChartTool 不做数据合理性校验（负数、零值、数量过多等） | `chart/tool.py` |

### 问题 3：ReAct 循环的 Guardrail 是补丁堆叠（★★★★☆ 严重）

**现状**：为了防止 LLM 无限循环，堆叠了大量启发式规则：

```python
# nodes.py 中的 guardrail 列表:
1. MAX_ITERATIONS 限制 (默认 100，.env 说 2)
2. 重复工具调用检测 (精确匹配 query)
3. 最大连续搜索次数限制 (代码 100，.env 说 2)
4. time 工具重复调用防护 (关键词匹配)
5. 连续文本响应计数 (>=2 次就算最终答案)
```

**问题**：
- `max_consecutive_search_calls` 默认值不一致：代码 `100`，`.env.example` `2`，README 说 `2`
- 去重使用精确匹配，LLM 微调 query 措辞就能绕过
- time 重复防护用关键词匹配 ("新闻", "天气", "today")，覆盖面有限
- 连续文本响应计数可能误判：LLM 第一步输出文本思考，第二步才是正确的 JSON
- 所有 guardrail 触发后都用 `_generate_forced_final_answer()` 强制结束，可能丢失有价值的部分结果

### 问题 4：流式架构过度复杂（★★★☆☆ 中等）

**现状**：SSE 事件类型多达 13 种，加上 block 协议、preamble buffer、control JSON buffer。

```
事件类型: token, thought, tool_start, tool_result, tool_summary, agent_step,
          block_start, block_chunk, block_end, chart_placeholder, chart_ready,
          chart, error
```

**问题**：
- `block_start/block_chunk/block_end` 协议在 token 外层又包了一层，增加复杂度
- preamble buffer（300 字符）延迟了首个 token 的显示
- `control_json_buffer` 和 `collecting_control_json` 状态机维护成本高
- 前端 `useChat.ts` 近 460 行，`handleParsedEvent` 处理 10+ 种事件类型
- `chart_placeholder` → `chart_ready` 两步协议在前端用 `_placeholder` 标志位追踪，容易泄漏

### 问题 5：Backend 价值有限（★★☆☆☆ 低）

**现状**：Spring Boot BFF 只做两件事：
1. JWT 认证（可以用 API Gateway 或中间件替代）
2. 代理 SSE 请求到 AI Service（纯转发）

**问题**：
- 增加部署复杂度和网络延迟
- WebClient 透传 SSE 时没有做错误处理或重连
- Application 层没有超时控制

### 问题 6：前端状态管理混乱（★★★☆☆ 中等）

**现状**：`useChat.ts` 中所有流式事件处理集中在一个巨大的 `handleParsedEvent` 函数中。

**问题**：
- `thinkingSteps` 用可变数组 + 命令式更新，状态来源分散（tool_start, tool_result, tool_summary 都在改同一个数组）
- `chartDatasForAssistant` 用 `_placeholder` 标志位追踪 placeholder → ready 转换
- `updateThinkingMessage()` 在多个分支中重复调用
- 自定义 SSE parser（`parseSseChunk`）手动处理 buffer 分割，多字节字符有风险

### 问题 7：遗留代码未清理（★★☆☆☆ 低）

- `chart_planner.py` / `chart_generator.py` / `content_composer.py`：旧的图表生成管线，已不使用
- `llm_node`：V0.2 兼容节点，当前图不使用
- Python 端 `charts/` 目录下的 ECharts builder（`LineChartBuilder` 等），前端自己构建 ECharts option，服务端版本未使用

---

## 三、整改方案

### 阶段一：切换到原生 Function Calling（解决 80% 的不稳定问题）

**目标**：让 LLM 通过 OpenAI-compatible 的 `tool_choice` 机制调用工具，彻底消除文本解析。

**改动**：

1. **`nodes.py` - agent_node 改造**
   - 使用 `ChatOpenAI.bind_tools(tools)` 绑定工具定义
   - 使用 `tool_choice="auto"` 让模型自动决策
   - 移除 `_parse_tool_call()`, `_strip_thought_tags()`, `_extract_tool_from_parsed()`
   - 从 `AIMessage.tool_calls` 读取工具调用意图
   - 保留 guardrail 逻辑（迭代上限、去重、连续搜索限制）

2. **`event_mapper.py` - 简化流式处理**
   - 移除 `process_stream_token_event()` 中的 JSON 过滤逻辑
   - 移除 `control_json_buffer` 和 `collecting_control_json` 状态机
   - 移除 `_filter_chart_denial()` — LLM 通过 function calling 不会输出 denial 文本
   - 移除 preamble buffer 机制

3. **`chat.py` - 简化路由**
   - 移除 `collecting_control_json`, `control_json_buffer`, `preamble_buffer` 变量
   - 移除 preamble flush 逻辑
   - 简化 blocking 协议

4. **Tool 定义标准化**
   - 每个 tool 提供标准的 OpenAI function schema
   - `ChartTool` 使用严格的 JSON Schema，不再支持 pipe 格式

**代码量预估**：删除 ~200 行补丁代码，新增 ~50 行标准化代码。

### 阶段二：图表生成重构

**目标**：图表生成稳定、可靠、可验证。

**改动**：

1. **ChartTool 改造**
   - 移除 pipe 格式支持，只接受结构化 JSON
   - 添加数据校验：类型检查、范围检查（value 不能全为 0）、数量限制（最多 50 个数据点）
   - 添加数据合理性警告（如所有值相同 → 建议用表格而非图表）
   - 返回详细的错误消息帮助 LLM 自我修正

2. **强制图表工具调用**
   - 在需要图表的场景，使用 `tool_choice={"type": "function", "function": {"name": "generate_chart"}}` 强制调用
   - 或者通过 system prompt 中的明确指令触发

3. **前端图表渲染增强**
   - 简化 `chart_placeholder` → `chart_ready` 为单事件（或超时兜底：3 秒后隐藏骨架）
   - 添加图表加载超时兜底
   - 添加图表错误状态展示

4. **System Prompt 优化**
   - 明确告诉 LLM 何时应该调用 generate_chart
   - 提供正确和错误的示例
   - 移除 "NEVER say you cannot" 这种负面指令（越强调不要做什么，LLM 越可能做）

### 阶段三：ReAct 循环优化

**目标**：减少 guardrail 补丁，用结构化机制替代启发式规则。

**改动**：

1. **统一 Guardrail 配置**
   - 修复 `max_consecutive_search_calls` 默认值不一致（统一为 3）
   - 所有 guardrail 参数集中到一个 `GuardrailConfig` dataclass
   - 从配置文件/env 统一加载

2. **去重改进**
   - 使用语义去重替代精确匹配（比较 tool_name + 核心关键词）
   - 或用编辑距离阈值（Levenshtein < 5 视为重复）

3. **智能终止判断**
   - 当 tool_result 已经包含足够信息时，注入 "sufficient information gathered" hint
   - 替代当前的关键词匹配（`browser:` / `chartType` in result）

4. **Time 工具简化**
   - 当前 time 工具被特殊处理（防止循环），改为 Agent 自动注入时间到 system prompt
   - time 工具只做时区转换，当前时间始终在 system prompt 中可用

### 阶段四：流式架构简化

**目标**：减少事件类型，简化前后端协议。

**改动**：

1. **事件类型精简**
   - 合并 `block_start/block_chunk/block_end` → 直接在 `token` 事件中流式传输
   - 合并 `chart_placeholder` + `chart_ready` → 单一 `chart` 事件
   - 移除 `agent_step` 作为独立事件，合入 `tool_result`

   ```
   精简后: token, thought, tool_start, tool_result, tool_summary, chart, error
   (从 13 种减少到 7 种)
   ```

2. **移除 preamble buffer**
   - 用 function calling 后，LLM 不会在工具调用前输出文本
   - 第一个 token 即时显示，无延迟

3. **前端 SSE 解析标准化**
   - 使用 `@microsoft/fetch-event-source` 或自定义 EventSource-like 封装
   - 或用原生 `EventSource` + POST polyfill

### 阶段五：架构简化（可选）

**目标**：减少不必要的服务层。

**方案 A**：Backend 瘦身
- 移除 Spring Boot BFF
- JWT 认证移到 AI Service 的 FastAPI 中间件
- 前端直连 AI Service

**方案 B**：Backend 增强
- 在 Backend 添加请求队列、限流、重试
- 添加 SSE 连接管理和心跳
- 如果有其他业务逻辑再保留

### 阶段六：TDD 质量保障

**目标**：每次改动有测试守护。

1. 为 ChartTool 添加数据校验的单元测试
2. 为 agent_node function calling 路径添加集成测试
3. 为 SSE event mapping 添加端到端测试
4. 前端添加 ChartRenderer 的 snapshot 测试

---

## 四、优先级与实施顺序

| 优先级 | 阶段 | 预期收益 | 风险 | 工作量 |
|--------|------|----------|------|--------|
| P0 | 阶段一：Function Calling | 解决 80% 不稳定性 | 中等（需测试各种 LLM 兼容性） | 3-5 天 |
| P0 | 阶段二：图表重构 | 图表生成可靠 | 低 | 2-3 天 |
| P1 | 阶段三：ReAct 优化 | 减少误终止 | 低 | 1-2 天 |
| P1 | 阶段四：流式简化 | 降低维护成本 | 中等（前后端协议变更） | 2-3 天 |
| P2 | 阶段五：架构简化 | 降低运维复杂度 | 高（需迁移认证逻辑） | 3-5 天 |
| P2 | 阶段六：TDD | 长期质量保障 | 低 | 持续 |

**建议**：阶段一和阶段二并行推进（不同文件，无冲突），阶段三、四依次进行，阶段五、六根据业务优先级决定。

---

## 五、风险提示

1. **Function Calling 兼容性**：当前默认使用 Qwen 模型，其 function calling 实现可能与 OpenAI 有差异。需要在 `extra_body` 中配置模型特定的参数。建议先用 `gpt-4o-mini` 或 `claude-haiku-4-5` 测试。

2. **协议变更**：阶段四的 SSE 协议简化会影响前端，需要前后端同步部署。

3. **向后兼容**：历史会话数据中可能包含旧格式的 ReAct 消息，`/history` 端点已有 `_is_internal_react_message()` 过滤，需确认兼容性。

4. **LangGraph Checkpoint**：切换到 function calling 后，LangGraph 的 checkpoint 中消息格式会变化（AIMessage.tool_calls 而非文本 JSON），需确认 PostgreSQL checkpoint 兼容。
