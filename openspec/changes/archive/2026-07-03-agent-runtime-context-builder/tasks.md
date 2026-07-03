## 1. Runtime Context Contracts

- [x] 1.1 新增运行时上下文模型：`ContextRequest`、`ContextFragment`、`AgentContext`
- [x] 1.2 新增 provider 抽象与注册机制，支持按优先级收集上下文片段
- [x] 1.3 新增 token budget/截断策略的最小实现与测试

## 2. Session Context MVP

- [x] 2.1 基于 `chat_message_repository` 实现 `SessionContextProvider`
- [x] 2.2 过滤内部消息与非用户可见工具噪音，只保留适合回灌的历史内容
- [x] 2.3 支持最近 N 轮历史加载与超预算裁剪

## 3. Builder Integration

- [x] 3.1 在 `AgentFactory` 接入 Context Builder，替代当前单纯模板变量替换的上下文拼接
- [x] 3.2 在 `graph/nodes.py` 接入结构化上下文，统一处理系统 prompt 与执行期上下文
- [x] 3.3 保持当前请求链路兼容：无历史、无可用 provider 时仍可正常响应

## 4. Future Provider Skeletons

- [x] 4.1 新增 Files / Memory / Knowledge provider 的空实现或 stub
- [x] 4.2 为后续 provider 预留 metadata 和 observability 字段

## 5. Verification

- [x] 5.1 新增单元测试：provider 合并顺序、裁剪策略、空 provider 行为
- [x] 5.2 新增集成测试：带 `conversation_id` 的请求可把最近会话历史注入运行时上下文
- [x] 5.3 运行受影响测试并记录结果