## Why

当前 Agent 运行时每次请求只拼接即时用户输入、工具描述和少量模板变量，缺少统一的上下文构建层。现状有三个直接问题：

- 会话历史虽然已经持久化到 `chat_messages`，但在运行时没有被结构化回灌给 Agent
- Agent prompt 组装分散在 `ai_service/core/agent_factory.py` 和 `ai_service/graph/nodes.py`，没有统一 token 预算和优先级策略
- V0.7 路线图定义了 Session / Files / Memory / Knowledge 四类上下文，但代码里还没有对应抽象，后续能力无法渐进接入

如果继续在各个节点手工拼 prompt，后续记忆、文件和知识检索都会变成横向复制粘贴，难以验证、难以限流，也难以演进为稳定的 Agent Runtime。

## What Changes

- 新增 `ContextBuilder` 主流程，统一收集、裁剪并组装运行时上下文
- 新增上下文契约：`ContextRequest`、`ContextFragment`、`AgentContext`
- 新增 `SessionContextProvider`，从会话历史仓储提取最近消息并生成可注入片段
- 新增 provider 注册/编排层，为 Files / Memory / Knowledge 预留可插拔接口
- 在 `AgentFactory` 和 Graph prompt 构建处接入 Context Builder，替代散落的字符串拼接
- 增加 token budget 与优先级合并规则，默认顺序为 Session > Files > Memory > Knowledge
- 为后续文件、记忆、知识能力先落地最小可运行骨架与测试，不在本 change 内引入完整 RAG 或上传系统

## Capabilities

### New Capabilities

- `agent-runtime-context-builder`: 为 Agent Runtime 构建会话/文件/记忆/知识四类上下文的统一编排层

### Modified Capabilities

- `agent-execution-plan`: 运行时 prompt 组装改为依赖结构化上下文，而不是节点内零散拼接

## Impact

- `ai_service/core/agent_factory.py`
- `ai_service/core/runtime.py`
- `ai_service/api/routes/chat.py`
- `ai_service/graph/nodes.py`
- `ai_service/db/chat_message_repository.py`
- 新增 `ai_service/context/` 或等价 runtime context 模块
- 新增对应单元测试与集成测试