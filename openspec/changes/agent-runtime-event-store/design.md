## Context

实时 Event Bus 解决运行中的事件分发，但排障和审计需要查询历史事件。项目已经使用 PostgreSQL 存储会话和 Agent 数据，因此 V0.8 的 Event Store 应复用现有数据库和连接配置，而不是引入新的外部组件。

本 change 依赖 Event Bus core，并消费 event sources 产生的 RuntimeEvent。它不负责创建事件源，不改变 SSE 实时链路。

## Goals / Non-Goals

**Goals:**
- 提供可选 RuntimeEvent 持久化。
- 复用 PostgreSQL 存储事件。
- 支持按 trace、conversation、事件类型和时间范围查询。
- 保证持久化失败不影响 Agent 主流程。

**Non-Goals:**
- 不引入 Redis、RabbitMQ、Kafka、ClickHouse 或新的数据库。
- 不提供复杂事件回放 UI。
- 不承诺跨服务分布式事件一致性。
- 不改变实时 SSE 发送路径。

## Decisions

1. Event Store 作为 Event Bus 订阅者实现。

   原因：这样持久化是可插拔消费者，不污染 LLM/Tool/Graph 发布点。关闭持久化时移除订阅即可。

   替代方案：在每个发布点直接写库。这样耦合高，也更容易影响主流程。

2. 复用 PostgreSQL 和现有连接池。

   原因：满足“不新增外部依赖组件”，并与会话持久化共用运维模型。

   替代方案：外部日志/事件存储更适合高吞吐分析，但超出 V0.8 范围。

3. 写入失败只记录错误，不反向传播。

   原因：事件持久化是可观测能力，不应让数据库短暂问题中断聊天。

   替代方案：强制写入成功后才继续执行。可审计更强，但用户体验风险过大。

4. 查询 API 先面向后端/调试用途。

   原因：当前没有完整观测 UI。先提供服务层或轻量 API，后续平台控制台再消费。

## Risks / Trade-offs

- [Risk] 高频事件增加数据库写入压力 -> [Mitigation] 支持开关、过滤事件类型，并避免默认持久化 token 级事件。
- [Risk] 事件 payload 体积过大或包含敏感信息 -> [Mitigation] 存储前裁剪 payload，并保留 metadata 标记。
- [Risk] 表结构后续演进 -> [Mitigation] 使用 JSONB 保存 payload/metadata，核心索引集中在 trace、conversation、type、timestamp。

## Migration Plan

1. 新增事件表初始化或迁移逻辑。
2. 实现 Event Store 订阅者和 repository。
3. 接入配置开关，默认可按环境决定启用。
4. 增加查询服务/API 和测试。
5. 验证数据库不可用时实时聊天仍可继续。

## Open Questions

- 默认是否启用事件持久化，还是仅在配置显式开启时启用？
- 事件保留周期和清理策略是否纳入 V0.8，还是留给后续可观测性阶段？
