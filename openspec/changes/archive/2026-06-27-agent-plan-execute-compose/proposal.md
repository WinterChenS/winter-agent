## Why

当前 Agent 采用被动反应式（Reactive）执行模式：LLM 在每一轮思考时即时决定调用什么 Tool，没有预先规划。这导致 Tool 调用顺序混乱、重复查询、重复生成图片、最终图文结构差。需要将执行范式从「边思考边执行」升级为「先规划、再执行、最后整理」的 Plan → Execute → Compose 三阶段模式，提升 Agent 整体执行质量。

## What Changes

- **新增 Planning Node**：在 Tool 执行前，LLM 首先生成结构化 JSON 执行计划（Execution Plan），计划中明确每个步骤需要的数据、Tool 和预期 Artifact。Planning 阶段允许使用只读 Tool（search、browser）辅助规划，但不生成正文、不生成图表。
- **新增 Execution Node**：严格按 Planning 生成的计划步骤依次执行，每步检查 Artifact 去重后调用 Tool，所有结果（图片、图表、搜索、JSON 等）统一保存到 State，不立即展示。
- **新增 Response Composer Node**：所有 Tool 执行完成后，LLM 根据用户问题 + Planning + Tool Results + Artifacts 统一生成图文自然穿插的专业报告。
- **实现 Artifact 去重机制**：基于 `(artifact_type, purpose_keywords)` 语义相似度进行宽松匹配，避免重复生成图片和重复调用 Tool。
- **简化路由**：移除 Router Agent，用户请求直接进入 Planning 阶段。意图判断的职责由 Planning 的 LLM 在生成计划时自然承担。
- **State 扩展**：新增 `execution_plan`、`execution_results`、`artifacts`、`current_plan_step`、`plan_phase` 字段。

## Capabilities

### New Capabilities

- `agent-execution-plan`: Plan → Execute → Compose 三阶段 Agent 执行工作流。Planning 生成结构化 JSON 计划，Execution 按计划步骤依次执行并去重，Composer 生成图文穿插的最终报告。
- `artifact-dedup`: Artifact 去重机制。基于 artifact type、purpose 的语义相似度进行宽松匹配，执行前检测已有 artifact 并直接引用，避免重复生成。

### Modified Capabilities

- `agent-chat-routing`: 移除 Router Agent 的多 Agent 路由逻辑，改为用户请求直通 Planning 节点。意图判断由 Planning 阶段的 LLM 在生成执行计划时承担。

## Impact

- `ai_service/graph/multi_agent_graph.py` — 主要改动：新增 planning/execution/composer 节点，移除 router→collaboration→merge 流程
- `ai_service/graph/state.py` — 新增 5 个 State 字段
- `ai_service/graph/nodes.py` — 新增 3 个 node 实现 + 去重工具函数
- `ai_service/api/routes/chat.py` — 适配新的 graph 拓扑和 node 输出
- `ai_service/core/router_agent.py` — 不再被主流程引用（保留文件，后续可移除）
- `ai_service/core/collaboration.py` — 不再被主流程引用（保留文件，后续可移除）
