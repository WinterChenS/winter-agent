# Week 5 工具分离 - 快速启动指南

## 📋 概览

本周完成了"工具过程"和"最终回答"的彻底分离，实现 OpenAI/Claude 级别的 Agent UI：

| 项 | 改进 |
|---|---|
| **工具显示** | 嵌入答案 → **独立消息区** |
| **消息类型** | user/assistant → **user/assistant/tool_summary** |
| **用户体验** | 混乱 → **清晰的分层展示** |

---

## 🏗️ 架构要点

### 数据流

```
Agent ReAct循环 → State(包含tool_steps) → SSE事件流 → BFF → 前端
                                          ↓
                                    tool_summary事件
                                          ↓
                                   创建独立消息
```

### 关键改动

| 层级 | 文件 | 改动 |
|-----|------|------|
| 后端 | `graph/state.py` | +`tool_steps: list[dict]` |
| 后端 | `graph/nodes.py` | +记录每个工具执行 |
| 后端 | `api/routes/chat.py` | +发送 `tool_summary` 事件 |
| BFF | `ChatController.java` | +支持嵌套 JSON 序列化 |
| 前端 | `types/chat.ts` | +`tool_summary` 消息 |
| 前端 | `hooks/useChat.ts` | +处理 tool_summary 事件 |
| 前端 | `components/ChatMessage.tsx` | +独立工�� UI |

---

## ✅ 验证清单

### ✓ 后端编译
```bash
cd /Volumes/work/projects/winter-agent/ai_service
python -m py_compile graph/state.py graph/nodes.py graph/graph.py api/routes/chat.py
# 输出: ✓ 所有文件编译成功
```

### ✓ Spring Boot 编译
```bash
cd /Volumes/work/projects/winter-agent/backend
mvn clean compile -q
# 应该能成功不输出错误
```

### ✓ 单元测试
```bash
cd /Volumes/work/projects/winter-agent/ai_service
python tests/test_tool_separation.py
# 输出: ✓ 所有测试通过！
```

---

## 🎯 工作流程

### 后端（Python）

#### 1️⃣ State 初始化
```python
{
    "messages": [...],
    "tool_steps": [],  # ← 新增，用于累积工具执行记录
}
```

#### 2️⃣ tool_node 执行记录
```python
# 每次工具执行后追加一条记录
tool_step = {
    "tool": "search",
    "input": "query text",
    "status": "completed",  # 或 "error"
    "elapsed_ms": 234,
    "error": None,  # 仅在失败时存在
}
state["tool_steps"] = state.get("tool_steps", []) + [tool_step]
```

#### 3️⃣ SSE 事件序列
```
token流 → 逐字渲染
    ↓
tool_start → 工具开始提示
    ↓
token流 → 继续回答
    ↓
tool_result → 工具完成信息
    ↓
token流 → 最终回答
    ↓
tool_summary → 完整工具步骤（流末尾）← 关键！
```

### 前端（React）

#### 1️⃣ 接收 tool_summary 事件
```typescript
if (parsed.type === 'tool_summary') {
  toolSummarySteps = parsed.steps;  // 存储完整步骤
}
```

#### 2️⃣ 创建独立消息
```typescript
addMessage({
  role: 'tool_summary',  // 新角色
  content: '工具执行步骤',
  toolSteps: toolSummarySteps,  // 完整数据
});
```

#### 3️⃣ 渲染两个消息
```
消息1（Assistant）
├─ 工具执行过程（可折叠，中间反馈）
└─ 最终回答（Markdown）

消息2（Tool Summary）← 【新增，独立区域】
├─ 🔍 工具执行步骤 (N)
├─ 🔎 search ✓ 完成 234ms
├─ 📝 input: query text
└─ ⏱️ 耗时展示
```

---

## 🧪 测试场景

### 场景 1: 单工具调用
```
输入: "搜索 LangGraph"
预期结果:
  - Assistant 消息：融合的回答
  - Tool Summary 消息：1个search工具，状态"completed"，耗时200-500ms
```

### 场景 2: 工具执行失败
```
输入: "搜索..." (无API密钥)
预期结果:
  - Tool Summary 消息：status="error"，显示红色背景
  - 错误信息展示：xxx not found
```

### 场景 3: 多轮对话
```
用户问题A → 工具1 → 回答A + Tool Summary（工具1）
用户问题B → 工具2 → 回答B + Tool Summary（工具2）
...
预期: 每轮都有独立的Tool Summary消息
```

---

## 📝 SSE 事件举例

### Token 事件
```json
{"type": "token", "token": "根", "content": "根"}
```

### Tool Start 事件  
```json
{
  "type": "tool_start",
  "toolName": "search",
  "content": "\n\n🛠️ 正在调用工具：search...\n"
}
```

### Tool Result 事件
```json
{
  "type": "tool_result",
  "toolName": "search",
  "content": "工具 `search` 执行完成，命中 3 条结果"
}
```

### Tool Summary 事件 ⭐
```json
{
  "type": "tool_summary",
  "steps": [
    {
      "tool": "search",
      "input": "LangGraph",
      "status": "completed",
      "elapsed_ms": 234,
      "error": null
    }
  ],
  "conversationId": "conv-123"
}
```

---

## 🔍 调试技巧

### 1. 检查 State 中的 tool_steps
```python
# 在 tool_node 中打印
print("Current tool_steps:", state.get("tool_steps", []))
```

### 2. 检查 SSE 事件流
```bash
# 在浏览器开发者工具中查看 Network → EventStream
# 应该能看到 tool_summary 事件
```

### 3. React DevTools 检查消息
```javascript
// 控制台查看消息数组
console.log(messages);
// 应该看到 role 为 "tool_summary" 的消息
```

### 4. 查看完整工具记录
```python
# api/routes/chat.py 第 156 行后添加
print("Tool steps to send:", tool_steps)
```

---

## 🚀 下一步

### 立即可做
- [ ] 在浏览器中测试UI效果（工具步骤卡片样式）
- [ ] 测试工具失败场景（错误着色）
- [ ] 验证耗时显示准确性

### 后续优化
- [ ] 工具执行时显示加载动画
- [ ] 支持多个工具并行执行
- [ ] 工具步骤持久化到数据库
- [ ] 工具链路DAG可视化

---

## 📚 相关文档

- [详细架构文档](./week5_tool_separation_architecture.md)
- [测试指南](../tests/test_tool_separation.py)
- [LangGraph State文档](https://langgraph.dev/docs/concepts/state)

---

## 💡 关键概念

**为什么要分离？**
- 用户关心"最终答案"，工具过程只是手段
- 独立显示让工具可复用给其他UI场景
- 结构化数据便于未来的工具链路追踪

**tool_summary 为什么在流末尾？**
- 确保所有回答token都已发送完成
- SSE流中最后一条事件，便于前端判断"流结束"
- 避免与中间的tool_start/tool_result重复

**为什么是dict而不是Message对象？**
- SSE是文本协议，需要JSON序列化
- 简化前端解析，不需要复杂的ORM映��
- 易于调试和查看原始数据

---

## ✨ 成就标志

✅ 后端编译成功
✅ BFF编译成功  
✅ 单元测试通过
✅ 核心数据结构实现
✅ SSE事件完整
✅ 前端类型定义更新
✅ UI组件准备就绪

**距离完全集成仅差前端环境启动！**

