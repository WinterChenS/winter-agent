## Context

当前系统采用三层架构：React 前端 (Tailwind CSS + Ant Design) → Spring Boot WebFlux 网关 → Python FastAPI LangGraph AI 服务。Chat 交互的 Message 模型、SSE 协议和 UI 组件均为早期快速迭代产物，缺乏标准化设计。本次改造在不改变整体架构定位的前提下，对 Chat 专用层进行标准化升级。

## Goals / Non-Goals

**Goals:**
- 建立跨三层统一的 Message Model（TypeScript + Java + Python）
- 标准化 SSE 事件协议为 `message.delta` / `message.tool_call` / `message.reasoning` / `message.done`
- 前端 Chat UI 模块化拆分（MessageBubble / ReasoningPanel / ToolCallPanel / MarkdownRenderer / 虚拟滚动）
- Agent 选择器支持动态多 Agent 切换，消息标注处理 Agent 身份
- Spring Boot 新增 Agent CRUD 代理 + agentId 透传
- Python GenerateRequest 新增 agentId，支持 graph 内 Agent 路由
- 消息历史持久化到 PostgreSQL，前端从 DB 加载完整历史（含 reasoning/toolCalls）

**Non-Goals:**
- 不改变 LangGraph 图拓扑核心逻辑（Router/Factory/Collaboration 策略不变）
- 不重写 AdminAgents 管理页面（保留 Ant Design）
- 不引入 WebSocket（保持 SSE）
- 不改变用户认证体系

## Decisions

### 1. 前端状态管理：Zustand

**选择**: Zustand，配合 `subscribeWithSelector` 中间件
**理由**: 
- 相比 Redux：API 简洁，无需 action creator/reducer 模板代码，bundle 体积小 (~1KB)
- 相比 Context：选择器级别的精准重渲染，避免流式更新时的整树 re-render
- 内置 `persist` 中间件可用于会话状态恢复
**备选**: Jotai（atom 粒度更细但流式场景下需更多 atom 协调）、Redux Toolkit（过度工程化）

### 2. 代码高亮：Shiki

**选择**: Shiki (通过 `shiki` npm 包，CDN 按需加载主题/语言)
**理由**:
- 语法准确度高于 highlight.js（基于 TextMate grammar，与 VS Code 一致）
- 支持 VS Code 主题生态
- 服务端/构建时可预编译，减少前端运行时开销
**风险**: 包体积大 (~10MB+) → **缓解**: 使用 `@shikijs/core` + 按需加载语言/主题；考虑构建时 tree-shake

### 3. 虚拟滚动：@tanstack/react-virtual

**选择**: `@tanstack/react-virtual`
**理由**: TanStack 生态成熟，支持动态高度行（消息气泡高度不一），API 简洁
**备选**: react-window（不支持动态高度）、react-virtuoso（功能全但 API 复杂）

### 4. SSE 事件协议升级策略

**选择**: **直接重命名，不做兼容过渡**
**理由**: 
- 当前系统仅内部使用，无外部消费者
- 旧事件命名（`token`/`tool_start`/`tool_result`）与新命名差异大，兼容过渡增加复杂度
- 前后端同时升级，一次性切换

**新事件映射**:
| 旧事件 | 新事件 | payload 变更 |
|--------|--------|-------------|
| `token` | `message.delta` | 新增 `messageId` 字段 |
| `tool_start` + `tool_result` | `message.tool_call` (合并) | 统一 `ToolCall { name, arguments, status, result }` |
| `reasoning_delta` / `thought` | `message.reasoning` | 标准化 payload |
| 流结束信号 (隐式) | `message.done` | `{ messageId, status: "done" }` |
| `tool_summary` | **废弃**（内嵌到 message.tool_call） | - |
| `agent_step` | **废弃**（合并到 message.delta 的 metadata） | - |
| `error` | **保留**，增加 `messageId` | 新增 `messageId` |

### 5. 消息持久化方案

**选择**: 复用 PostgreSQL（Python 端已有 checkpointer），新增 `chat_messages` 表
**Schema**:
```sql
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY,
  conversation_id UUID NOT NULL,
  role VARCHAR(16) NOT NULL,           -- user | assistant | system
  content TEXT NOT NULL DEFAULT '',
  reasoning TEXT,                       -- JSON: reasoning content
  tool_calls JSONB,                     -- JSON: ToolCall[]
  status VARCHAR(16) DEFAULT 'done',   -- streaming | done | error
  agent_id VARCHAR(64),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_messages_conv ON chat_messages(conversation_id, created_at);
```
**理由**: 
- 复用已有 PostgreSQL，不引入新数据库
- JSONB 存储 reasoning/toolCalls，灵活且支持索引查询
- Python 端负责写入，Spring Boot 透传查询

### 6. Agent 路由设计

```
前端选择 Agent → POST /api/chat { agentId, message, conversationId }
  → Spring Boot 鉴权 + 透传
    → Python AI Service:
        GET /api/v1/agents/{agentId} → 获取 Agent 定义
        → 注入 active_agent 到 graph state
        → RouterAgent 根据 agentId 路由到对应 Agent Node
        → SSE 事件流回传（含 agentId 标识）
```

## Risks / Trade-offs

- **[风险] SSE 协议一次性切换导致短期前后端不兼容** → 缓解：同一分支内开发，feature branch 合并前完成三层升级
- **[风险] Shiki 包体积影响首屏加载** → 缓解：按需加载 + 构建时 tree-shake + lazy import（非首屏渲染路径）
- **[风险] 消息历史表写入增加 AI Service 延迟** → 缓解：异步写入，不阻塞 SSE 流；批量写入优化
- **[取舍] 放弃旧事件兼容性换取代码简洁性** → 影响范围可控（无外部消费者）

## Migration Plan

1. Feature branch 内开发，不发布中间态
2. 分三层顺序实施：Python 协议层 → Spring Boot 网关 → 前端 UI
3. 每个 task 完成后 git commit，task 验证通过后勾选
4. 合并到 main 时三层一起上线
5. 无需数据库迁移脚本（新表，非修改已有表）

## Open Questions

1. Shiki 具体使用 `@shikijs/core` + 手动按需加载，还是 `shiki` 全量包 + CDN？→ 实施时根据构建配置决定
2. 消息历史表由 Python 直接写入还是通过 Spring Boot API 写入？→ 建议 Python 直接写入（减少一跳延迟）
