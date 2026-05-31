# 图表问题渲染改造计划（评审版）

## 1. 目标与边界

### 1.1 核心目标
- 当用户问题明确要求图表（如“用K线图展示A股走势”）时，系统应返回**结构化图表数据**并在前端渲染。
- 保持现有文本流式体验不回退：图表是增强能力，不是替代。
- 方案要支持后续多 Agent 扩展，避免把单一业务逻辑写死在某一层。

### 1.2 首期范围（MVP）
- 仅支持 2 类图：
  - `candlestick`（A 股 K 线，OHLCV）
  - `line`（时间序列折线）
- 仅支持“对话中内嵌渲染图表”，不做独立图表页面。
- 仅改造当前主链路：`frontend -> backend(BFF) -> ai_service`。

### 1.3 非目标（本期不做）
- 不做图表编辑器、复杂技术指标（MACD/布林带等）配置化 UI。
- 不做多图联动与高级交互（缩放联动、十字光标同步等）。
- 不做历史消息的完整可回放图形缓存（仅保证不报错）。

---

## 2. 当前问题复盘（对应你提出的诉求）

### 2.1 稳定性问题
- SSE 解析与事件语义耦合，容易出现“有事件但内容没落地”的情况。
- 错误事件与 JSON 解析异常存在混淆，可能导致错误被吞掉。

### 2.2 渲染问题
- 当前 UI 以文本为主，缺少一类“图表消息”模型，导致图表只能被描述，不能被渲染。
- 工具过程与回答内容混在同一消息上下文，扩展更多消息类型时会继续膨胀。

### 2.3 架构问题
- 事件协议缺少版本和可扩展字段，不利于多 Agent / 多工具并行场景。
- `ai_service` 中路由层承担较多事件编排责任，后续加能力容易变成“巨型 if/else”。

---

## 3. 目标架构（解耦方向）

### 3.1 分层职责
- `ai_service`：负责智能决策、工具执行、输出标准化领域事件（包括图表事件）。
- `backend(BFF)`：负责协议透传/兼容与边界校验，不承载 AI 业务决策。
- `frontend`：负责事件消费与消息渲染，基于消息类型进行组件化展示。

### 3.2 关键原则
- **结构化事件优先**：图表数据必须走 `chart_data` 事件，不靠文本解析。
- **文本兜底**：任何图表失败都保留可读答案，不中断会话。
- **向后兼容**：未知事件类型忽略，旧字段继续可用。
- **可观测**：事件中加入基础跟踪字段，为后续多 Agent 调试准备。

---

## 4. SSE 事件协议扩展（V1）

### 4.1 通用事件信封
所有 SSE `data:` 负载建议统一为：

```json
{
  "type": "token | tool_start | tool_result | tool_summary | chart_data | chart_error | error",
  "schemaVersion": "1.0",
  "conversationId": "string",
  "agentId": "string",
  "turnId": "string",
  "spanId": "string",
  "payload": {}
}
```

说明：
- 本期可先保留现有平铺字段（兼容），新增 `payload` 作为演进方向。
- `agentId/turnId/spanId` 本期可选填，先预留协议位。

### 4.2 图表相关事件

#### `chart_data`
```json
{
  "type": "chart_data",
  "schemaVersion": "1.0",
  "conversationId": "xxx",
  "chartId": "chart_xxx",
  "payload": {
    "chart": {
      "chartType": "candlestick",
      "title": "上证指数近30日K线",
      "description": "数据来源与时间范围说明",
      "xAxis": { "type": "time", "label": "日期" },
      "series": [
        {
          "name": "上证指数",
          "data": [
            {"ts": 1716307200000, "open": 3110.1, "high": 3132.0, "low": 3098.5, "close": 3128.4, "volume": 230000000}
          ]
        }
      ],
      "meta": {
        "symbol": "000001.SH",
        "interval": "1d",
        "timezone": "Asia/Shanghai"
      }
    }
  }
}
```

#### `chart_error`
```json
{
  "type": "chart_error",
  "schemaVersion": "1.0",
  "conversationId": "xxx",
  "chartId": "chart_xxx",
  "payload": {
    "code": "DATA_SOURCE_UNAVAILABLE",
    "message": "行情源暂不可用，已降级为文字总结"
  }
}
```

---

## 5. 图表 Schema 设计（前后端统一）

### 5.1 顶层对象
- `chartId: string`
- `schemaVersion: string`
- `chartType: "candlestick" | "line"`
- `title: string`
- `description?: string`
- `xAxis: { type: "time" | "category", label?: string }`
- `series: Array<Series>`
- `meta?: Record<string, unknown>`

### 5.2 数据约束
- 时间统一毫秒时间戳 `ts`。
- 数值字段必须是 number。
- 每次返回点数上限建议 `<= 500`，超限裁剪并在 `meta.truncated=true` 标注。
- 禁止返回 HTML/script 等可执行内容。

### 5.3 前端容错规则
- `chartType` 不支持 -> 显示“暂不支持该图表类型”的降级卡片。
- `series` 为空 -> 显示“暂无可视化数据”的占位卡片。
- 字段校验失败 -> 记录日志并降级文本展示。

---

## 6. 分阶段里程碑与任务拆分

## M0：方案评审（当前阶段）
**输出物**
- 本文档确认。
- 事件协议与 Schema 冻结（V1）。

**验收**
- 你确认“范围、优先级、图表类型、数据源策略”。

---

## M1：协议与类型打通（不引入新图表库）

### 前端（`frontend`）
- 扩展 `Message` 类型：新增 `role: 'chart'` 或新增 `chart` 字段。
- 扩展 `useChat` 的 SSE 事件分支，新增消费 `chart_data/chart_error`。
- 新增 `ChartMessage` 占位组件（先 JSON 摘要 + 状态文案，不正式画图）。

### 后端（`backend`）
- 扩展 `GenerateResponse` 字段（兼容反序列化）：`chartId/schemaVersion/chart/payload`。
- `ChatController.toPayloadJson` 增加图表字段白名单透传。

### AI 服务（`ai_service`）
- 在 `chat.py` 中支持发出 `chart_data/chart_error`。
- 保持 `token` 与 `tool_*` 行为不变。

**验收标准**
- 发出模拟 `chart_data` 时，前端可稳定展示占位卡片。
- 非图表问题行为不回退。

---

## M2：A股 K 线能力接入

### AI 服务
- 新增工具：`stock_kline`（放在 `ai_service/tools/stock_kline/`）。
- 工具输入：`symbol`, `interval`, `start`, `end`, `limit`。
- 工具输出：标准化 `chart` 数据（符合 V1 Schema）。
- `agent_node` 提示词策略：
  - 包含“走势/K线/蜡烛图/均线/图表”等意图时优先调用 `stock_kline`。
  - 工具失败返回 `chart_error` + 文本总结。

### 前端
- 接入图表库（候选：`lightweight-charts` 优先于 `echarts`，因为 K 线场景轻量且专精）。
- 实现正式 `ChartMessage` 组件：渲染 `candlestick/line`。

**验收标准**
- 输入“上证指数近30日K线”可稳定渲染 K 线。
- 图表渲染失败不影响文本回答。

---

## M3：稳定性与可扩展增强

### 稳定性
- 增加超时、重试、熔断策略（工具层）。
- 增加事件大小与点数限制。
- 增加会话级 feature flag：`enableChartRendering`。

### 可扩展（多 Agent 预留）
- 事件中持续填充 `agentId/turnId/spanId/parentSpanId`。
- 将 `chat.py` 的事件拼装逻辑拆分为独立模块：
  - `event_envelope.py`
  - `event_mapper.py`
  - `chart_event_builder.py`

**验收标准**
- 压测下不会出现明显“丢图表事件/卡死”问题。
- 关闭开关后完全回落到文本模式。

---

## 7. 详细改造清单（按仓库位置）

### 7.1 Frontend
- `frontend/src/types/chat.ts`
  - 扩展消息与事件类型定义。
- `frontend/src/hooks/useChat.ts`
  - 新增 `chart_data/chart_error` 事件消费与消息入列逻辑。
- `frontend/src/components/ChatMessage.tsx`
  - 拆分：文本消息、工具摘要、图表消息独立渲染分支。
- `frontend/src/components/MessageList.tsx`
  - 透传 `chart` 相关字段。
- `frontend/src/components/ChartMessage.tsx`（新增）
  - 专职图表渲染组件。

### 7.2 Backend（BFF）
- `backend/src/main/java/com/example/aichat/model/GenerateResponse.java`
  - 增加 `chartId/schemaVersion/chart/payload`。
- `backend/src/main/java/com/example/aichat/controller/ChatController.java`
  - `toPayloadJson` 透传上述字段，避免手工 JSON 丢字段。

### 7.3 AI Service
- `ai_service/tools/stock_kline/*`（新增）
  - 工具实现与注册。
- `ai_service/graph/nodes.py`
  - 更新图表意图判断与工具调用策略。
- `ai_service/api/routes/chat.py`
  - 发射 `chart_data/chart_error` 事件。
- `ai_service/schemas.py` 或 `api/schemas.py`
  - 增加图表 Schema 校验模型。

---

## 8. 测试计划

### 8.1 单元测试
- Frontend：
  - `useChat` 对 `chart_data/chart_error` 处理。
  - `ChartMessage` 对异常数据的降级渲染。
- Backend：
  - `GenerateResponse` 映射测试。
  - `toPayloadJson` 图表字段透传测试。
- AI Service：
  - `stock_kline` 输入校验与输出格式测试。
  - `chat.py` 事件序列测试（token + chart + summary）。

### 8.2 集成测试
- Mock 行情源，验证端到端：
  - 图表正常渲染
  - 工具失败时文本兜底
  - 非图表问题无图表事件

### 8.3 回归测试
- 历史消息加载不报错。
- 原有工具步骤展示和文本流式体验不回退。

---

## 9. 风险与回滚

### 9.1 风险
- 行情源不稳定导致图表数据缺失。
- 图表库引入后包体增大与首屏变慢。
- 结构化协议变更导致三端兼容问题。

### 9.2 缓解
- 工具层缓存 + 超时 + 重试上限。
- 图表组件按需加载（懒加载）。
- 协议版本化 + 未知字段忽略策略。

### 9.3 回滚
- 前端 feature flag 关闭图表渲染。
- AI 服务停止发 `chart_*` 事件，仅保留文本。
- BFF 保持向后兼容字段，不中断已有流程。

---

## 10. 需要你确认的决策点（确认后执行）

1. 首期图表库选型：
   - A. `lightweight-charts`（更适合 K 线，轻量）
   - B. `echarts`（图表类型多，体积更大）
2. 首期数据源策略：
   - A. 先 Mock 数据打通链路，再接真实行情源
   - B. 直接接真实行情源
3. 首期功能范围：
   - A. 仅 A 股 K 线
   - B. A 股 K 线 + 折线
4. 是否启用 feature flag（建议启用）

> 你确认以上 4 个决策后，我再按该计划分阶段实施，并每个阶段提交可验证结果。

