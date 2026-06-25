## Why

当前工具系统有三个核心问题：(1) 添加新工具需修改 3 个文件（Tool 类、main.py 注册、nodes.py 的 prompt），不具备可扩展性；(2) 缺少代码执行沙箱，Agent 无法进行数据分析、图表预处理等计算密集型操作；(3) ReAct 循环每次只能调用一个工具，数据收集阶段耗时长。这三个问题阻碍了 Winter Agent 向标准 AI Agent 平台演进。

## What Changes

- **标准化工具注册机制**：引入工具插件的自动发现与注册，添加新工具只需创建一个文件，无需修改其他代码
- **统一工具定义格式**：采用 OpenAI function/tool schema 作为工具描述标准，自动生成 LLM prompt，消除手动维护
- **代码执行沙箱**：支持 Agent 编写和执行 Python 代码，用于数据分析、图表数据预处理、文件处理等场景
- **并行工具调用**：单次 ReAct 迭代支持同时调用多个独立工具，减少数据收集阶段的往返次数
- **工具结果标准化**：统一工具返回格式，降低 LLM 理解不同工具结果的成本

## Capabilities

### New Capabilities

- `tool-auto-discovery`: 工具插件通过文件约定自动发现并注册到 ToolRegistry，无需手动在 main.py 注册
- `tool-schema-standard`: 统一的工具定义格式（OpenAI function schema），自动生成 LLM 系统提示词中的工具描述
- `code-sandbox`: 沙箱化的 Python 代码执行能力，支持数据分析、数据预处理、图表数据生成
- `parallel-tool-execution`: 单次 ReAct 迭代中并行调用多个无依赖关系的工具

### Modified Capabilities

<!-- 无已有 spec 需要修改 -->

## Impact

- **ai_service/tools/**：重构 BaseTool、ToolRegistry，新增 auto-discovery 和 schema 标准
- **ai_service/graph/nodes.py**：agent_node 工具调用协议从单工具 JSON 升级为支持并行调用的格式
- **ai_service/graph/graph.py**：可能需要新增并行执行节点或使用 LangGraph Send API
- **ai_service/main.py**：移除手动工具注册代码，改为自动发现
- **ai_service/tools/sandbox/**：新增代码沙箱工具模块
- **前端**：无需改动（工具调用过程对前端透明）
