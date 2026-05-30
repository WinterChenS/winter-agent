# Week 3 - Tool Registry 设计与实操

> 本周目标：搭建 `Tool Registry` 最小骨架（P0），为 Week 4 的 ReAct 图升级做准备。

---

## 0) 本周目标

- 理解 Tool 抽象：工具为什么要统一接口
- 理解 Registry 职责：注册、发现、调用，而不是“做路由决策”
- 完成最小目录骨架：`tools/base.py`、`tools/registry.py`、`tools/search/tool.py`
- 用一个可复现的 Mock Search Tool 证明“可注册、可调用、可扩展”

---

## 1) 你本周要做什么（Checklist）

- [ ] 新建目录与文件骨架
- [ ] 定义 `BaseTool` 接口（元数据 + async execute）
- [ ] 实现 `ToolRegistry`（register/get/list/invoke）
- [ ] 实现 `SearchTool`（先 mock 返回）
- [ ] 写一个最小演示（注册 + 调用 + 异常路径）
- [ ] 记录设计结论与问题

---

## 2) 推荐目录结构

```text
ai_service/
  tools/
    __init__.py
    base.py
    registry.py
    search/
      __init__.py
      tool.py
```

---

## 3) 核心设计（先理解再写代码）

### 3.1 `BaseTool` 需要什么

推荐统一字段：

- `name`: 工具唯一名称（如 `search`）
- `description`: 给 Agent/开发者看的能力说明
- `input_schema`: 输入结构定义（后续可用于校验）
- `execute(payload)`: 异步执行入口

你可以先采用这个返回结构（建议统一成字典，避免后续返工）：

```text
{
  "ok": true,
  "data": {...},
  "error": null
}
```

失败时：

```text
{
  "ok": false,
  "data": null,
  "error": {
    "code": "TOOL_EXECUTION_ERROR",
    "message": "...",
    "retryable": true
  }
}
```

### 3.2 `ToolRegistry` 负责什么

只负责“管理工具”，不负责“决定用哪个工具”。

必须有：

- `register(tool)`：注册，且防重复名
- `get(name)`：按名获取
- `list_tools()`：列出可用工具
- `invoke(name, payload)`：可选，但初学阶段建议加，调用路径更清晰

---

## 4) 本周最小演示目标

你至少要验证下面 3 条：

1. 可以成功注册 `SearchTool`
2. 可以通过 `invoke("search", {"query": "langgraph"})` 拿到结果
3. 重复注册同名工具时会报错（不是静默覆盖）

---

## 5) 常见错误（提前避坑）

- 把“路由决策”写进 Registry（错误）
- 工具返回格式不统一，后续 `tool_result` 难处理
- 在 `graph/nodes.py` 里硬编码工具名，导致难扩展
- 不处理重复注册，后续调试非常痛苦

---

## 6) Week 3 验收标准

满足以下即通过：

- 能解释 `BaseTool` 和 `ToolRegistry` 各自职责
- 新增工具不需要改核心图结构代码
- `register/get/list/invoke` 都能工作
- 缺失工具、重复工具注册有明确异常反馈
- 有一份最小演示记录（输入/输出）

---

## 7) 你的提交模板（完成后发我）

```markdown
# Week 3 复盘

## 1) 我实现了什么
- 

## 2) 我的 Tool 接口设计
- 

## 3) Registry 设计要点
- 

## 4) 最小演示结果
- 成功路径：
- 失败路径（重复注册/未找到工具）：

## 5) 我卡住的问题
- 
```

---

## 8) 现在就开始的第一个动作

先完成文件骨架（空文件也可以），然后我带你逐个文件写实现。

---

## 9) 当前已落地实现（可直接验证）

- `tools/base.py`
- `tools/registry.py`
- `tools/search/tool.py`
- `tools/demo_registry.py`

运行演示：

```bash
python -m tools.demo_registry
```

你会看到：

1. 注册成功
2. `search` 调用成功
3. 非法入参返回统一错误结构
4. 重复注册报错
5. 未注册工具报错

