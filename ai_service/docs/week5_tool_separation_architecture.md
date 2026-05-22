# Week 5+ 工具过程与最终回答彻底分离架构

## 概述

本周实现了 **"工具过程"和"最终回答"的彻底分离**，创造了两个独立的消息区域，达到 OpenAI/Claude Agent UI 的专业观感。

### 核心改進

| 项目 | 改进前 | 改进后 |
|------|-------|--------|
| **工具步骤展示** | 嵌入在助手回答中 | 独立的"工具执行步骤"消息区 |
| **消息角色** | user / assistant | user / assistant / **tool_summary** |
| **工具数据** | 从文本中解析 | 完整结构化的数组 |
| **用户体验** | 工具信息混入答案 | 工具步骤独立展示，答案清晰聚焦 |

---

## 架构设计

### 后端流程（Python LangGraph）

```
User Message
    ↓
┌─────────────────────┐
│   graph.astream()   │
└─────────────────────┘
    ↓
┌──────────────────────────────┐
│  State（包含 tool_steps）      │
│  ├── messages                │
│  ├── current_tool            │
│  ├── tool_input              │
│  ├── tool_result             │
│  └── tool_steps ← 新增        │
│      ├── tool: "search"      │
│      ├── input: "query"      │
│      ├── status: "completed" │
│      ├── elapsed_ms: 234     │
│      └── error (optional)    │
└──────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│   SSE 事件流（6 种事件类型）          │
│ 1. token         → 逐字渲染答案     │
│ 2. tool_start    → 工具开始（警告）   │
│ 3. tool_result   → ���具完成（中间状态）│
│ 4. error         → 错误信息        │
│ 5. tool_summary  → 最终结构化步骤   │
│ 6. (implicit)    → 图执行完成      │
└─────────────────────────────────────┘
    ↓
Spring Boot BFF
    ↓
React Frontend
```

### State 结构（新增字段）

```python
class State(TypedDict):
    messages: Annotated[List, add_messages]  # 对话历史
    current_tool: str | None                 # 当前工具名
    tool_input: dict | None                  # 工具入参
    tool_result: str | None                  # 工具结果
    reasoning_steps: list[str]               # 调试跟踪
    iteration_count: int                     # 循环计数
    tool_steps: list[dict]  # ← NEW!
```

### tool_steps 记录格式

每个工具执行后，tool_node 记录一条：

```python
{
    "tool": "search",
    "input": "LangGraph tutorial",
    "status": "completed",  # 或 "error"
    "elapsed_ms": 234,
    "error": None           # 仅当 status="error" 时存在
}
```

---

## 实现细节

### 1. 后端：tool_node 记录步骤

**文件**: `graph/nodes.py` (lines 131-174)

```python
async def tool_node(state: State) -> dict:
    start_time = time.time()  # 记录开始时间
    
    # 执行工具...
    result = await registry.invoke(tool_name, tool_input)
    
    # 计算耗时
    elapsed_time = time.time() - start_time
    
    # 创建步骤记录
    tool_step_record = {
        "tool": tool_name,
        "input": tool_input.get("query", ""),
        "status": "completed" if result.get("ok") else "error",
        "elapsed_ms": int(elapsed_time * 1000),
        "timestamp": start_time,
    }
    if status == "error":
        tool_step_record["error"] = error_msg
    
    # 追加到状态
    new_tool_steps = state.get("tool_steps", []) + [tool_step_record]
    
    return {
        "tool_result": result_str,
        "tool_steps": new_tool_steps,  # ← 保存完整的步骤列表
        ...
    }
```

### 2. SSE 事件流：发送工具摘要

**文件**: `api/routes/chat.py` (lines 60-173)

```python
# 在流的末尾，图执行完成时捕获最终状态
final_state = None

async for event in graph.astream_events(...):
    ...
    # 捕获最终状态
    elif event_type == "on_chain_end" and event_name == "agent":
        final_state = event.get("data", {}).get("output", {})

# 流结束后，发送统一的工具摘要事件
if final_state:
    tool_steps = final_state.get("tool_steps", [])
    if tool_steps:
        yield {
            "data": json.dumps({
                "type": "tool_summary",
                "steps": tool_steps,  # 完整的工具步骤数组
                "conversationId": request.conversation_id,
            })
        }
```

### 3. BFF 层：转发完整负载

**文件**: `backend/.../ChatController.java`

更新 `GenerateResponse` 记录，添加 `steps` 字段：

```java
public record GenerateResponse(
    String type,
    String token,
    String content,
    @JsonProperty("toolName") String toolName,
    String error,
    String conversationId,
    @JsonProperty("steps") java.util.List<java.util.Map<String, Object>> steps  // ← NEW
) {}
```

在 `toPayloadJson()` 方法中使用 ObjectMapper 完整序列化，支持嵌套对象：

```java
if (response.steps() != null && !response.steps().isEmpty()) {
    payload.put("steps", response.steps());
}
return objectMapper.writeValueAsString(payload);  // 完整 JSON 序列化
```

### 4. 前端 useChat Hook：接收 tool_summary

**文件**: `frontend/src/hooks/useChat.ts` (lines 5-20, 232-239)

```typescript
interface StreamPayload {
  type?: 'token' | 'tool_start' | 'tool_result' | 'tool_summary' | 'error';
  steps?: Array<{
    tool: string;
    input: string;
    status: 'completed' | 'error';
    elapsed_ms: number;
    error?: string;
  }>;
}

// 处理 tool_summary 事件
} else if (parsed.type === 'tool_summary') {
  if (parsed.steps && Array.isArray(parsed.steps)) {
    toolSummarySteps = parsed.steps;
  }
}

// 流结束后，创建独立的工具摘要消息
if (toolSummarySteps && toolSummarySteps.length > 0) {
  addMessage({
    role: 'tool_summary',
    content: '工具执行步骤',
    toolSteps: toolSummarySteps,
  });
}
```

### 5. 前端 Message 类型：支持 tool_summary 角色

**文件**: `frontend/src/types/chat.ts`

```typescript
export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool_summary';  // ← NEW
  content: string;
  timestamp: number;
  toolSteps?: Array<{                           // ← NEW
    tool: string;
    input: string;
    status: 'completed' | 'error';
    elapsed_ms: number;
    error?: string;
  }>;
}
```

### 6. 前端 ChatMessage 组件：独立工具摘要 UI

**文件**: `frontend/src/components/ChatMessage.tsx`

```typescript
export const ChatMessage: React.FC<ChatMessageProps> = ({
  role,
  content,
  toolSteps = [],
}) => {
  const isToolSummary = role === 'tool_summary';
  
  // 工具摘要消息使用紫色背景，显示完整的工具执行信息
  return (
    <div className={`rounded-2xl px-4 py-3 ${
      isToolSummary ? 'bg-purple-50 border border-purple-200' : '...'
    }`}>
      {isToolSummary && (
        <div>
          <button onClick={() => setShowToolSteps(!showToolSteps)}>
            🔍 Agent 工具执行步骤 ({displaySteps.length})
          </button>
          
          {showToolSteps && (
            <div className="space-y-3">
              {displaySteps.map(step => (
                <div className={step.status === 'completed' 
                  ? 'border-green-200 bg-green-50' 
                  : 'border-red-200 bg-red-50'}>
                  <div className="flex items-center gap-2">
                    <span>{getToolIcon(step.tool)}</span>
                    <span className="font-semibold">{step.tool}</span>
                    <span className="text-xs">
                      {step.status === 'completed' ? '✓ 成功' : '✗ 失败'}
                    </span>
                    <span className="text-xs ml-auto">{step.elapsed_ms}ms</span>
                  </div>
                  {step.input && <div className="text-xs">输入：{step.input}</div>}
                  {step.error && <div className="text-xs font-mono">错误：{step.error}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
```

---

## 用户体验流程

### 场景：用户问"今天最新消息"

1. **用户输入**
   ```
   用户: "今天有哪些大新闻？"
   ```

2. **后端处理**
   - Agent 决策：需要使用 search 工具
   - 记录到 State: `tool_steps = []`
   - search 工具执行：234ms
   - 追加： `tool_steps = [{tool: "search", input: "...", status: "completed", elapsed_ms: 234}]`

3. **SSE 事件序列**
   ```javascript
   // 1. Token 事件（逐字流式）
   {type: "token", token: "根"},
   {type: "token", token: "据"},
   ...
   
   // 2. 工具开始（中间提示）
   {type: "tool_start", toolName: "search"}
   
   // 3. 工具完成（中间反馈）
   {type: "tool_result", toolName: "search", content: "工具 `search` 执行完成..."}
   
   // 4. 最终回答继续
   {type: "token", token: "最"},
   {type: "token", token: "新"},
   ...
   
   // 5. 最后发送完整工具步骤（流末尾）
   {
     type: "tool_summary",
     steps: [
       {
         tool: "search",
         input: "今天 2024年1月 最新大新闻",
         status: "completed",
         elapsed_ms: 234
       }
     ]
   }
   ```

4. **前端渲染**
   
   **消息 1**（Assistant 消息）
   ```
   ┌─────────────────────────────────┐
   │ Agent 执行过程（1 步）[展开/收起] │
   │ 整合后的最终回答（Markdown）     │
   │ 根据最新消息，���年...             │
   └─────────────────────────────────┘
   ```
   
   **消息 2**（工具摘要消息 - 分离的）
   ```
   ┌────────────────────────────────┐
   │ 🔍 Agent 工具执行步骤 (1) [▼]   │
   │ ┌──────────────────────────────┤
   │ │ 🔎 search        ✓ 成功  234ms │
   │ │ 输入：今天 2024年1月...       │
   │ └──────────────────────────────┤
   └────────────────────────────────┘
   ```

---

## 核心优势

### 1. **视觉分离**
- 工具步骤不再污染最终答案
- 每个工具操作有独立的卡片，颜色区分（成功/失败）
- 用户一眼看清"Agent 做了什么"和"最终答案是什么"

### 2. **完整的元数据**
- 保留耗时���息（elapsed_ms）
- 错误原因可被清晰展示
- 工具输入可被审查和调试

### 3. **可折叠的详情**
- 默认简洁（只显示"🔍 Agent 工具执行步骤 (1)"��
- 点击展开看完整细节
- 降低认知负荷

### 4. **消息历史友好**
- 未来可以持久化 `tool_summary` 消息到数据库
- 加载历史时，工具步骤作为独立消息恢复
- 不需要重新解析文本

### 5. **后端干净**
- 不再在 `messages` 中混入工具步骤文本
- State 数据结构清晰
- SSE 事件类型明确（tool_start/tool_result 只是中间反馈，最终汇总到 tool_summary）

---

## 开发检查清单

### 后端（已完成 ✓）
- [x] State 添加 `tool_steps: list[dict]` 字段
- [x] tool_node 记录执行步骤到 tool_steps
- [x] SSE 事件流在最后发送 `tool_summary` 事件
- [x] Spring Boot ChatController 支持嵌套 JSON 序列化
- [x] GenerateResponse 添加 steps 字段
- [x] Python 编译验证 ✓
- [x] Spring Boot 编译验证 ✓

### 前端（已完成 ✓）
- [x] Message 类型添加 tool_summary 角色和 toolSteps 字段
- [x] StreamPayload 接口添加 tool_summary 事件类型和 steps 字段
- [x] useChat Hook 处理 tool_summary 事件
- [x] useChat Hook 创建独立的 tool_summary 消息
- [x] ChatMessage 组件支持 tool_summary 角色
- [x] ChatMessage 组件渲染工具步骤卡片（带颜色、耗时、错误信息）

---

## 测试指南

### 1. 单工具场景
```
用户: "搜索 LangGraph 的最新文档"
预期:
- 助手消息：融合后的答案
- 工具摘要消息：1 个 search 工具步骤（成功，~200-500ms）
```

### 2. 多工具场景（如支持批量调用）
```
用户: "今天的新闻和当前时间"
预期:
- 助手消息：融合答案
- 工具摘要消息：2 个步骤（search + time）
```

### 3. 工具失败场景
```
用户: "搜索..." (API 密钥不存在)
预期:
- 工具摘要消息中该步骤显示红色背景
- status: "error"
- error: "TAVILY_API_KEY not found"
```

### 4. 历史加载验证
```
加载之前的对话
预期:
- 工具摘要消息作为单独消息恢复
- toolSteps 数据完整
```

---

## 后续改进方向

### Priority 1
- [ ] 工具并行执行支持（如果 Agent 支持）
- [ ] 工具执行时的实时动画（旋转加载器）
- [ ] 历史记录中工具步骤的持久化

### Priority 2
- [ ] 工具执行的详细日志展开（显示完整 stdout/stderr）
- [ ] 成功/失败 retry 按钮
- [ ] 工具链路追踪（DAG 可视化）

### Priority 3
- [ ] 工具成本统计（API call count）
- [ ] A/B 测试：内联 vs 分离工具显示
- [ ] 用户偏好设置

---

## 代码变更摘要

| 文件 | 变更 |
|------|------|
| `graph/state.py` | +1 field: `tool_steps` |
| `graph/nodes.py` | +import time, 修改 tool_node，记录步骤 |
| `api/routes/chat.py` | +捕获最终状态，发送 tool_summary 事件 |
| `backend/ChatController.java` | +支持嵌套 JSON 序列化 |
| `backend/GenerateResponse.java` | +steps ��段 |
| `frontend/types/chat.ts` | +tool_summary 角色和 toolSteps 字段 |
| `frontend/hooks/useChat.ts` | +处理 tool_summary，创建独立消息 |
| `frontend/components/ChatMessage.tsx` | +tool_summary 组件，独立 UI |

**总计**: ~250 行新增/修改代码

---

## 总结

通过彻底分离工具过程和最终回答，实现了：
- ✓ 专业级的 Agent UI 观感
- ✓ 用户快速区分结果和过程
- ✓ 完整的结构化工具元数据
- ✓ 可扩展的历史记录模型
- ✓ 未来工具链路追踪的基础

**下周任务**: 可选升级为工具并行支持 + 实时动画反馈。

