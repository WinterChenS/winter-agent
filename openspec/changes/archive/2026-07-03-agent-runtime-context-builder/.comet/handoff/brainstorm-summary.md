# Brainstorm Summary

## Confirmed

- change: `agent-runtime-context-builder`
- workflow: `full`
- design scope: 首版只做 backend runtime 基础设施
- implementation target: Session Context + Context Builder + Assembler + Injector
- deferred to later providers: Files / Memory / Knowledge 先保留 provider 契约与 stub，不在本轮做真实数据源接入

## Constraints

- 复用现有 `chat_message_repository.get_messages_by_conversation()`，避免重复建设历史存储
- 不修改现有 SSE 协议
- 不引入向量库、RAG 或上传系统作为本轮阻塞依赖

## Candidate Design Direction

- 已确认做法：新增独立 `context/` 模块，集中定义 request/fragment/context 模型、provider 协议、assembler 与 injector
- 接入点：`ai_service/api/routes/chat.py` 提供 request context，`ai_service/core/agent_factory.py` 与 `ai_service/graph/nodes.py` 消费 builder 输出

## Selected Approach

- 采用方案 B：独立 context 模块统一编排

## Open Design Point

- graph 执行期上下文与静态 agent prompt 的拼接边界，需要在 design doc 中明确，避免重复注入历史消息