# V0.3 实施拆解计划（逐文件、逐阶段）

> 本文是 `multi_agent_architecture_blueprint_v0_2_to_v2_0.md` 的 V0.3 落地执行版。
> 目标：先完成“统一契约 + 职责下沉 + 最小治理”，为 V0.4+ 多 Agent/RAG/MCP/Skills/Sandbox 打地基。

---

## 0. V0.3 目标与范围

## 0.1 目标（必须达成）
1. 统一事件协议：所有 SSE 事件走 `EventEnvelope`。
2. 统一能力抽象：Tool 通过 `Capability` 元数据接入，不再写死分支。
3. `chat.py` 从“事件业务逻辑中心”降级为“生命周期编排层”。
4. `nodes.py` 工具结果格式化逻辑下沉到 normalizer。
5. 引入最小 `PolicyGate`（白名单、参数长度、超时覆盖）。
6. 全链路补齐 `trace_id/turn_id/span_id`。

## 0.2 非目标（V0.3 不做）
- 不实现多 Agent 协作路由（V0.4）。
- 不实现完整 RAG 管道（V0.5）。
- 不接入 MCP、Skills 引擎、Sandbox 执行（V0.6+）。

---

## 1. 交付物清单（Deliverables）

1. 代码：AI Service 主体改造（P0）。
2. 代码：BFF + Frontend 协议兼容改造（P1）。
3. 文档：事件契约文档 + 兼容矩阵。
4. 测试：单测与最小集成验证。
5. 验收：V0.3 验收清单逐项勾选通过。

---

## 2. 分阶段实施（P0 / P1 / P2）

## P0：核心地基（必须先做）

### P0-1 统一事件信封（EventEnvelope）

**改动文件**
- 新增 `ai_service/domain/event_envelope.py`
- 修改 `ai_service/api/routes/chat.py`

**新增接口**
- `EventEnvelope`（TypedDict 或 dataclass）
- `build_envelope(event_type, context, payload, compat_fields)`
- 快捷函数：
  - `envelope_token(...)`
  - `envelope_tool_start(...)`
  - `envelope_tool_result(...)`
  - `envelope_tool_summary(...)`
  - `envelope_error(...)`

**固定字段（必填）**
- `type`
- `schemaVersion`
- `conversationId`
- `turnId`
- `agentId`
- `traceId`
- `spanId`
- `timestamp`
- `payload`

**兼容策略**
- 过渡期双写旧字段：`content/token/toolName/steps/error`（顶层保留）。

**测试用例**
- `ai_service/tests/test_event_envelope.py`
  - `test_required_fields_present`
  - `test_compat_flat_fields_dual_write`
  - `test_payload_preserves_structured_data`

**验收标准**
- `chat.py` 内不再出现散乱事件 JSON 拼装。
- 每条 SSE 事件都带 trace/turn/span。

---

### P0-2 Capability 抽象

**改动文件**
- 新增 `ai_service/domain/capability.py`
- 修改 `ai_service/tools/base.py`
- 修改 `ai_service/tools/registry.py`

**新增模型**
- `CapabilityKind = tool | skill | mcp`
- `CapabilitySpec`
  - `name`
  - `version`
  - `kind`
  - `input_schema`
  - `output_schema`
  - `timeout_ms`
  - `retry_policy`
  - `policy_tags`
- `CapabilityCall`
- `CapabilityResult`

**接口调整**
- `ToolRegistry.list_capabilities()`
- `ToolRegistry.invoke_capability(call: CapabilityCall)`
- 保留旧接口 `list_tools()/invoke()` 作为兼容层。

**测试用例**
- `ai_service/tests/test_capability_registry.py`
  - `test_tool_to_capability_projection`
  - `test_invoke_capability_success`
  - `test_unknown_capability_returns_standard_error`

**验收标准**
- 新增工具只需注册元数据，不需改核心流程分支。

---

### P0-3 `chat.py` 事件映射下沉

**改动文件**
- 新增 `ai_service/api/events/event_types.py`
- 新增 `ai_service/api/events/event_mapper.py`
- 修改 `ai_service/api/routes/chat.py`

**新增抽象**
- `EventMapContext`
  - `conversation_id`
  - `turn_id`
  - `trace_id`
  - `agent_id`
  - `span_id`
- `map_langgraph_event_to_envelopes(event, ctx)`
- `emit_final_summary_envelope(final_state, ctx)`

**实施要点**
- `chat.py` 仅负责：请求入参校验、graph 启动、迭代事件、异常兜底。
- 事件类型识别与 payload 构建全部迁移到 mapper。

**测试用例**
- `ai_service/tests/test_chat_event_mapper.py`
  - `test_map_chat_model_stream_to_token`
  - `test_map_tool_start_event`
  - `test_map_tool_end_event`
  - `test_emit_tool_summary_from_final_state`

**验收标准**
- Route 代码体积明显下降，职责清晰。

---

### P0-4 `nodes.py` 工具结果规范化下沉

**改动文件**
- 新增 `ai_service/graph/normalizers/tool_result.py`
- 修改 `ai_service/graph/nodes.py`

**下沉接口**
- `normalize_tool_result_for_prompt(tool_result: str | None) -> str`
- `normalize_tool_step_record(...) -> dict`

**说明**
- 将 `_sanitize_tool_result_for_prompt` 从 `nodes.py` 中迁出。
- `agent_node` 和 `tool_node` 只调用 normalizer，不再包含大段格式化规则。

**测试用例**
- `ai_service/tests/test_tool_result_normalizer.py`
  - `test_invalid_json_returns_safe_fallback`
  - `test_time_tool_context`
  - `test_search_result_compaction`
  - `test_error_result_normalization`

**验收标准**
- normalizer 可独立测试；`nodes.py` 复杂度下降。

---

### P0-5 最小 PolicyGate

**改动文件**
- 新增 `ai_service/policy/models.py`
- 新增 `ai_service/policy/gate.py`
- 修改 `ai_service/graph/nodes.py`（或 capability 执行层）

**最小策略能力**
- `tool_whitelist`
- `max_query_len`
- `timeout_override_ms`

**执行流程**
- 调工具前：`decision = gate.evaluate(call, context)`
- `deny`：返回标准错误 `CapabilityResult` + `error` envelope
- `allow`：正常执行

**测试用例**
- `ai_service/tests/test_policy_gate.py`
  - `test_deny_non_whitelisted_tool`
  - `test_deny_oversized_query`
  - `test_allow_default_tools`

**验收标准**
- 任意工具调用必经 gate，拒绝结果结构一致。

---

### P0-6 trace/span 补齐

**改动文件**
- 新增 `ai_service/observability/trace.py`
- 修改 `ai_service/graph/state.py`
- 修改 `ai_service/api/routes/chat.py`

**新增字段**
- `trace_id`
- `turn_id`
- `span_id`
- `parent_span_id`
- `active_agent`

**新增方法**
- `ensure_trace_context(conversation_id) -> TraceContext`
- `new_span(parent_span_id, name) -> span_id`

**测试用例**
- `ai_service/tests/test_trace_context.py`
  - `test_trace_created_per_turn`
  - `test_tool_span_parent_is_agent_span`

**验收标准**
- 同一轮 token/tool/error/summary 事件可通过 trace 串联。

---

## P1：跨层协议收敛（V0.3 完整可用）

### P1-1 Backend（BFF）Envelope 透传

**改动文件**
- `backend/src/main/java/com/example/aichat/model/GenerateResponse.java`
- `backend/src/main/java/com/example/aichat/controller/ChatController.java`

**新增字段**
- `schemaVersion`
- `turnId`
- `agentId`
- `traceId`
- `spanId`
- `payload`

**测试建议**
- `GenerateResponseSerdeTest`
- `ChatControllerPayloadTest`

**验收标准**
- BFF 不丢 envelope 字段。
- 旧字段仍可输出（兼容前端旧版本）。

---

### P1-2 Frontend Envelope 优先消费

**改动文件**
- `frontend/src/types/chat.ts`
- `frontend/src/hooks/useChat.ts`
- `frontend/src/components/ChatMessage.tsx`

**改造点**
- `StreamPayload` 增加 `schemaVersion/turnId/agentId/traceId/spanId/payload`。
- UI 消费优先级：`payload` > 旧平铺字段。
- 未识别事件类型时忽略但记录日志。

**测试建议**
- 增加 `frontend/src/services/eventMapper.ts` 纯函数并测试。

**验收标准**
- 新旧协议都能消费，界面无回归。

---

## P2：治理增强（V0.3 收尾）

### P2-1 配置化策略

**改动文件**
- `ai_service/config.py`
- `ai_service/main.py`

**新增配置**
- `POLICY_TOOL_WHITELIST`
- `POLICY_MAX_QUERY_LEN`
- `POLICY_TIMEOUT_OVERRIDE_MS`
- `TRACE_ENABLED`

**验收标准**
- 策略参数可环境变量配置，无需改代码。

---

### P2-2 文档与兼容矩阵

**新增文档**
- `ai_service/docs/v0_3_event_contract.md`
- `ai_service/docs/v0_3_compatibility_matrix.md`

**矩阵维度**
- 字段：AI Service -> BFF -> Frontend
- 事件：`token/tool_start/tool_result/tool_summary/error`
- 兼容：旧字段/新字段/双写窗口

**验收标准**
- 任意团队成员可按文档复现实装与联调。

---

## 3. V0.3 任务排期建议（按顺序）

1. P0-1 EventEnvelope
2. P0-6 TraceContext（建议与 P0-1 同步）
3. P0-3 chat.py 下沉 event mapper
4. P0-4 nodes.py 下沉 normalizer
5. P0-2 Capability 抽象
6. P0-5 PolicyGate
7. P1 Backend 透传
8. P1 Frontend 兼容消费
9. P2 配置化与文档矩阵

> 原则：先协议、再职责、后治理；先 AI Service 内聚，再跨层联调。

---

## 4. 风险与回滚策略

### 4.1 风险
- 双协议迁移阶段字段混用导致解析歧义。
- 事件信封改造引入前端显示缺口。
- PolicyGate 过严导致工具误拒绝。

### 4.2 缓解
- 双写窗口：至少保留两周旧字段。
- 所有新事件先灰度到开发环境。
- Policy 默认“宽松 + 白名单最小集”，逐步收紧。

### 4.3 回滚
- 通过 feature flag 关闭 envelope-only 路径。
- Route 可临时回退到旧 `_stream_data` 输出（保留一版）。

---

## 5. V0.3 验收清单（上线前必须全绿）

- [ ] AI Service SSE 全事件带 `traceId/turnId/spanId`
- [ ] `chat.py` 不再包含复杂事件业务逻辑
- [ ] `nodes.py` 工具结果规范化逻辑已模块化
- [ ] Tool 以 `Capability` 方式可注册/调用
- [ ] 所有工具调用均经过 `PolicyGate`
- [ ] Backend 可透传 envelope 与旧字段
- [ ] Frontend 能消费 envelope 且无 UI 回归
- [ ] 单测与最小联调测试通过

---

## 6. 下一步（你确认后执行）

你确认本拆解后，下一步我会输出：
1. `V0.3-Phase1` 逐文件改造 patch 计划（每个文件具体改哪些函数）。
2. 对应测试清单（先 AI Service，再 BFF，再 Frontend）。
3. 每阶段完成后的验证命令与联调脚本。

