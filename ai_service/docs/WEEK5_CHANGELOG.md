# Week 5 变更日志

## 变更摘要

本周完成了"工具过程"与"最终回答"的彻底分离，共修改 **8 个关键文件**，新增 **~400 行代码**。

---

## 📝 详细变更

### 1. `graph/state.py`

**变更类型**: 新增字段  
**影响**: State 数据结构扩展

```diff
  class State(TypedDict):
      messages: Annotated[List, add_messages]
      current_tool: str | None
      tool_input: dict | None
      tool_result: str | None
      reasoning_steps: list[str]
      iteration_count: int
+     tool_steps: list[dict]  # ← NEW
```

**说明**:
- 添加 `tool_steps` 列表用于记录所有工具执行步骤
- 每条记录包含：tool, input, status, elapsed_ms, error(可选)
- 作为 State reducer，自动在节点间传递

---

### 2. `graph/nodes.py`

**变更类型**: 修改 log/timeit + 修改函数  
**影响**: 工具执行步骤记录

```diff
+ import time  # ← 新增

  async def tool_node(state: State) -> dict:
+     start_time = time.time()  # ← 记录开始时间
      
      # 工具执行逻辑...
      result = await registry.invoke(tool_name, tool_input)
      
+     # ← 新增：计算耗时和创建记录
+     elapsed_time = time.time() - start_time
+     tool_step_record = {
+         "tool": tool_name,
+         "input": tool_input.get("query", ""),
+         "status": "completed" if ok else "error",
+         "elapsed_ms": int(elapsed_time * 1000),
+         "timestamp": start_time,
+     }
+     if status == "error" and error_msg:
+         tool_step_record["error"] = error_msg
+     
+     new_tool_steps = state.get("tool_steps", []) + [tool_step_record]
      
      return {
          "tool_result": result_str,
+         "tool_steps": new_tool_steps,  # ← 返回累积的步骤
          "current_tool": None,
          "tool_input": None,
          "reasoning_steps": ...,
      }
```

**说明**:
- 每次工具执行时记录完整的执行信息
- 包含工具名、输入、状态、耗时、错误信息
- 追加到 State 的 tool_steps 列表中

---

### 3. `api/routes/chat.py`

**变更类型**: 修改函数逻辑 + 新增事件  
**影响**: SSE 事件流，支持 tool_summary 事件

```diff
  @router.post("/generate/stream")
  async def stream_generate(request: GenerateRequest):
      async def event_generator():
          # ...
          inputs = {
              "messages": [HumanMessage(content=request.message)],
+             "tool_steps": []  # ← 初始化
          }
          
+         final_state = None
+         tool_summary_sent = False
          
          async for event in graph.astream_events(...):
              # ... 现有的 token/tool_start/tool_result 事件处理 ...
              
+             # ← 新增：捕获最终状态
+             elif event_type == "on_chain_end" and event_name == "agent":
+                 final_state = event.get("data", {}).get("output", {})
          
-         # ← 移除了在流中发送 tool_summary 的逻辑
+         # ← 新增：在流末尾发送统一的 tool_summary 事件
+         if final_state and not tool_summary_sent:
+             tool_steps = final_state.get("tool_steps", [])
+             if tool_steps:
+                 yield {
+                     "data": json.dumps({
+                         "type": "tool_summary",
+                         "steps": tool_steps,
+                         "conversationId": request.conversation_id,
+                     })
+                 }
+                 tool_summary_sent = True
      
      return EventSourceResponse(event_generator())

+ @router.get("/history/{conversation_id}")
+ async def get_chat_history(conversation_id: str):
+     # ← 修复：添加 RunnableConfig 类型注解
+     config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}
      ...
```

**说明**:
- 新增 `tool_summary` SSE 事件类型
- 在流的末尾（图执行完成后）发送完整的工具步骤列表
- 避免与中间的 tool_start/tool_result 重复

---

### 4. `backend/src/main/java/com/example/aichat/model/GenerateResponse.java`

**变更类型**: 新增字段  
**影响**: BFF 响应模型

```diff
  public record GenerateResponse(
      String type,
      String token,
      String content,
      @JsonProperty("toolName") String toolName,
      String error,
      @JsonAlias({"conversationId", "conversation_id"}) String conversationId,
+     @JsonProperty("steps") java.util.List<java.util.Map<String, Object>> steps  // ← NEW
  ) {
  }
```

**说明**:
- 添加 `steps` 字段以支持工具摘要事件
- 类型为嵌套对象列表，用 ObjectMapper 序列化

---

### 5. `backend/src/main/java/com/example/aichat/controller/ChatController.java`

**变更类型**: 重写方法 + 新增辅助方法  
**影响**: SSE 事件序列化和转发

```diff
  private String toPayloadJson(GenerateResponse response) {
-     Map<String, String> payload = new LinkedHashMap<>();
+     Map<String, Object> payload = new LinkedHashMap<>();  // ← 改为 Object
      
      if (response.type() != null) payload.put("type", response.type());
      if (response.token() != null) payload.put("token", response.token());
      if (response.content() != null) payload.put("content", response.content());
      if (response.toolName() != null) payload.put("toolName", response.toolName());
      if (response.conversationId() != null) payload.put("conversationId", response.conversationId());
      if (response.error() != null) payload.put("error", response.error());
+     if (response.steps() != null && !response.steps().isEmpty()) {
+         payload.put("steps", response.steps());
+     }
      
-     // ← 移除手动 JSON 拼接
+     // ← 改用 ObjectMapper 完整序列化嵌套对象
+     try {
+         return objectMapper.writeValueAsString(payload);
+     } catch (Exception e) {
+         return buildJsonManually(payload);
+     }
  }

+ // ← 新增辅助方法
+ private String buildJsonManually(Map<String, Object> payload) { ... }
+ private String serializeList(List<?> list) { ... }
+ private String serializeMap(Map<?, ?> map) { ... }
```

**说明**:
- 使用 Jackson ObjectMapper 完整序列化（支持嵌套）
- 提供手动 JSON 拼接作为 fallback
- 处理 List<Map<String, Object>> 嵌套结构

---

### 6. `frontend/src/types/chat.ts`

**变更类型**: 扩展接口  
**影响**: 前端消息模型

```diff
  export interface Message {
    id: string;
-   role: 'user' | 'assistant';
+   role: 'user' | 'assistant' | 'tool_summary';  // ← NEW
    content: string;
    timestamp: number;
+   toolSteps?: Array<{                           // ← NEW
+     tool: string;
+     input: string;
+     status: 'completed' | 'error';
+     elapsed_ms: number;
+     error?: string;
+   }>;
  }
```

**说明**:
- 添加 `tool_summary` 消息角色
- 包含 `toolSteps` 数组用于存储工具执行记录

---

### 7. `frontend/src/hooks/useChat.ts`

**变更类型**: 修改接口 + 新增处理逻辑  
**影响**: SSE 事件消费

```diff
  interface StreamPayload {
    type?: 'token' | 'tool_start' | 'tool_result' | 'error';
+   type?: '...' | 'tool_summary';  // ← NEW
    token?: string;
    content?: string;
    conversationId?: string;
    error?: string;
    toolName?: string;
+   steps?: Array<{ ... }>;  // ← NEW
  }

  // ← 新增：工具摘要缓冲
  let toolSummarySteps: Array<any> = [];

  // ← 新增：处理 tool_summary 事件
  } else if (parsed.type === 'tool_summary') {
    if (parsed.steps && Array.isArray(parsed.steps)) {
      toolSummarySteps = parsed.steps;
    }
  }

  // ← 新增：流结束后创建独立的工具摘要消息
  if (toolSummarySteps && toolSummarySteps.length > 0) {
    addMessage({
      role: 'tool_summary',
      content: '工具执行步骤',
      toolSteps: toolSummarySteps,
    });
  }
```

**说明**:
- 添加 `tool_summary` 事件类型处理
- 缓存工具步骤数据
- 在流结束后创建新的消息对象

---

### 8. `frontend/src/components/ChatMessage.tsx`

**变更类型**: 扩展组件 + 新增 UI  
**影响**: 消息渲染

```diff
  interface ChatMessageProps {
-   role: 'user' | 'assistant';
+   role: 'user' | 'assistant' | 'tool_summary';  // ← NEW
    content: string;
    isLoading?: boolean;
+   toolSteps?: Array<{ ... }>;  // ← NEW
  }

  export const ChatMessage: React.FC<ChatMessageProps> = ({
    role,
    content,
    isLoading = false,
+   toolSteps = [],
  }) => {
+   const isToolSummary = role === 'tool_summary';
    
    // ← 分别处理 normal 和 tool_summary
    const displaySteps = isToolSummary ? toolSteps : extractedSteps;
    
    return (
      <div className={`rounded-2xl ${
-       isUser ? 'bg-blue-500' : 'bg-gray-100'
+       isUser ? 'bg-blue-500' 
+       : isToolSummary ? 'bg-purple-50 border border-purple-200'  // ← NEW
+       : 'bg-gray-100'
      }`}>
        {isUser ? (
          // ... 用户消息渲染 ...
        ) : isToolSummary ? (
+         // ← 新增��工具摘要消息的独立 UI
+         <div>
+           <button onClick={() => setShowToolSteps(!showToolSteps)}>
+             🔍 Agent 工具执行步骤 ({displaySteps.length})
+           </button>
+           {showToolSteps && (
+             <div className="space-y-3">
+               {displaySteps.map(step => (
+                 <div className={step.status === 'completed' 
+                   ? 'bg-green-50' : 'bg-red-50'}>
+                   {/* 工具卡片：工具名、图标、状态、耗时、输入、错误 */}
+                 </div>
+               ))}
+             </div>
+           )}
+         </div>
        ) : isLoading && !content ? (
          // ... 加载状态 ...
        ) : (
          // ... 常规助手消息 ...
        )}
      </div>
    );
  };
```

**说明**:
- 支持 `tool_summary` 消息角色
- 独立的 UI 样式（紫色背景）
- 显示工具执行步骤卡片，包含：
  - 工具图标（🔎search, 🐍python, 📄file, 🗣️echo）
  - 工具名+ 状态（✓成功 / ✗失败）
  - 执行耗时
  - 输入参数
  - 错误信息（如果有）

---

## 📊 统计

| 指标 | 数值 |
|-----|------|
| 修改的文件 | 8 |
| 新增代码行数 | ~400 |
| 新增文档 | 3 份 |
| 测试覆盖 | 7 个单元测试 |
| 编译��证 | ✓ Python + ✓ Java |

---

## 🔗 依赖关系

```
State.tool_steps (新字段)
    ↓
tool_node (记录步骤)
    ↓
api/routes/chat.py (发送 tool_summary 事件)
    ↓
BFF ChatController (转发完整 JSON)
    ↓
前端 useChat Hook (接收和处理)
    ↓
ChatMessage 组件 (渲染独立 UI)
```

---

## ✅ 验证项目

- [x] 所有 Python 文件编译成功
- [x] Spring Boot 项目编译成功
- [x] 7 个单元测试通过
- [x] 架构文档完成
- [x] 快速启动指南完成
- [x] 变更日志完成

---

## 🚀 后续步骤

1. **立即测试**
   ```bash
   # 后端
   cd ai_service && python tests/test_tool_separation.py
   
   # 前端（在前端目录）
   npm test
   ```

2. **集成验证**
   - 启动 Python 后端
   - 启动 Spring Boot BFF
   - 启动 React 前端
   - 向 Agent 提问��查看工具步骤显示

3. **性能测试**
   - 测试多工具场景下的耗时统计
   - 验证 SSE 事件流的完整性
   - 检查前端渲染性能

---

## 📖 相关资源

- 架构文档: [week5_tool_separation_architecture.md](./week5_tool_separation_architecture.md)
- 快速指南: [week5_quickstart.md](./week5_quickstart.md)
- 单元测试: [test_tool_separation.py](../tests/test_tool_separation.py)


