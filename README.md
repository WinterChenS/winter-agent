# Winter Agent

面向工程的 AI Agent 平台——从基础对话系统演进为完整的智能体框架，支持工具调用、多智能体编排、图表生成和可执行计划。

## 架构

```
React 前端 (port 3000)
    │  HTTP/SSE
    ▼
Spring Boot BFF (port 8080)  ——  JWT 认证 · 反向代理
    │  HTTP/SSE
    ▼
Python AI 服务 (port 8000)  ——  FastAPI · LangGraph · 工具调用
    │
    ▼
PostgreSQL · MinIO · LLM API
```

## 核心特性

- **流式对话** — LLM 到浏览器的全链路 token 级 SSE 流式传输，支持思考过程 (reasoning) 展示
- **工具调用** — JSON Schema 约束的 ReAct 循环，内置护栏（最大迭代、连续搜索去重、策略门控），支持并行工具执行
- **工具生态** — Web 搜索 (Tavily)、页面抓取 (HTTPX + BeautifulSoup)、Python 沙箱执行 (subprocess)、时间工具，注册表自动发现
- **图表生成** — 声明式 ChartSpec → matplotlib 渲染 → MinIO 上传，企业级调色板（中英文颜色名称），支持条形图/折线图/饼图/散点图/直方图/热力图
- **计划-执行-合成流水线** — 生成结构化执行计划 → 顺序执行（含图表代码生成+验证+去重）→ 合成含嵌入图表的综合报告
- **多智能体编排** — 关键词+LLM 兜底路由，三种协作策略：顺序链 / 并行扇出 / 监督分解合成
- **策略门控** — 可配置的工具白名单、查询长度限制、超时覆盖，带审计日志
- **智能体管理** — 前端 CRUD 界面，系统提示编辑、工具选择、启用/禁用、克隆
- **JWT 认证** — Spring Boot 过滤器链 + 前端 AuthContext
- **会话持久化** — PostgreSQL 存储 + LangGraph checkpoint + 会话历史侧边栏

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 · TypeScript · Vite · Tailwind CSS · Zustand · ECharts · CodeMirror |
| BFF | Spring Boot 3.4 · WebFlux · Java 21 · Spring Security · JPA |
| AI 服务 | Python 3.12 · FastAPI · LangGraph · LangChain · SSE |
| 数据库 | PostgreSQL 16 · MinIO |
| 可观测性 | LangSmith (可选) |
| 部署 | Docker Compose · Traefik · Nginx |

## 快速开始

### 环境要求

- Java 21+
- Python 3.12+
- Node.js 20+
- PostgreSQL 16
- [Ollama](https://ollama.com) 或其他兼容 OpenAI API 的 LLM 服务

### Docker 部署 (推荐)

```bash
cp .env.example .env
# 编辑 .env 填入 API_KEY、BASE_URL、MODEL 等

docker compose up -d
```

### 本地开发

```bash
# 设置环境变量后一键启动
export API_KEY=your-api-key
export BASE_URL=https://api.openai.com/v1
export MODEL=gpt-4

./start-dev.sh
```

### 分别启动

**前端**
```bash
cd frontend && npm install && npm run dev
# http://localhost:3000
```

**后端**
```bash
cd backend && mvn spring-boot:run
# http://localhost:8080
```

**AI 服务**
```bash
cd ai_service
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
# http://localhost:8000
```

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `API_KEY` | LLM API 密钥 | — |
| `BASE_URL` | LLM API 地址 | `https://api.openai.com/v1` |
| `MODEL` | 模型名称 | `gpt-3.5-turbo` |
| `POSTGRES_URI` | 数据库连接串 | `postgresql://postgres:postgres@localhost:5432/aichat` |
| `TAVILY_API_KEY` | Tavily 搜索 API Key | — |
| `LANGCHAIN_API_KEY` | LangSmith API Key (可选) | — |
| `MAX_CONSECUTIVE_SEARCH_CALLS` | 单轮最多连续搜索次数 | `2` |

## 项目结构

```
winter-agent/
├── frontend/              # React 前端
│   └── src/
│       ├── features/ai-chat/   # 聊天模块 (SSE Store · 消息渲染 · 工具面板)
│       ├── views/AgentManagement/  # 智能体管理 (CRUD · 提示编辑器)
│       └── contexts/AuthContext.tsx # JWT 认证
├── backend/               # Spring Boot BFF
│   └── src/main/java/com/example/aichat/
│       ├── controller/    # ChatController · AgentController · AuthController
│       ├── client/        # AIClient · AgentClient (WebClient 代理)
│       └── config/        # SecurityConfig · JwtAuthFilter
├── ai_service/            # Python AI 服务
│   ├── api/routes/        # REST + SSE 路由
│   ├── core/              # AgentFactory · RouterAgent · Collaboration
│   ├── graph/             # LangGraph 图 (nodes · validators · multi-agent)
│   ├── tools/             # 工具系统 (search · browser · sandbox · time)
│   ├── chart/             # 图表模块 (ChartSpec · matplotlib · MinIO)
│   └── tests/             # 测试套件 (30+ 文件)
├── docker-compose.yml     # 容器编排 (traefik · postgres · ai-service · backend · frontend)
└── start-dev.sh           # 本地开发启动脚本
```

## API

### `POST /api/chat/stream` (SSE)

流式对话接口。

```json
{
  "message": "帮我查一下今天的天气",
  "conversationId": "optional-uuid"
}
```

### `GET /api/chat/history/{conversationId}`

查询会话历史。

```json
{
  "messages": [
    { "role": "user", "content": "你好" },
    { "role": "assistant", "content": "你好！有什么可以帮你的？" }
  ]
}
```

### 智能体管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/agents` | 获取智能体列表 |
| `POST` | `/api/v1/agents` | 创建智能体 |
| `PUT` | `/api/v1/agents/{id}` | 更新智能体 |
| `DELETE` | `/api/v1/agents/{id}` | 删除智能体 |
| `POST` | `/api/v1/agents/{id}/toggle` | 启用/禁用 |
| `POST` | `/api/v1/agents/{id}/clone` | 克隆智能体 |

## 路线图

### 第一阶段：Agent Runtime（V0.1 ~ V1.0）

> 目标：打造稳定、可扩展的 Agent Runtime，为所有 Agent 提供统一运行时能力。

| 版本 | 状态 | 描述 |
|------|------|------|
| V0.1 | ✅ 完成 | 基础对话 + SSE 全链路流式响应 |
| V0.2 | ✅ 完成 | 多轮会话 + LangGraph Checkpoint + LangSmith 可观测性 |
| V0.3 | ✅ 完成 | Tool Runtime（ReAct + Tool Registry + Strategy Guard） |
| V0.4 | ✅ 完成 | 多 Agent 路由 + 顺序 / 并行 / Supervisor 协作模式 |
| V0.5 | ✅ 完成 | Planner → Execute → Synthesize 执行流水线 + ChartSpec 图表生成 |
| V0.6 | 🚧 进行中 | 原生 Function Calling Runtime（替代文本解析） |
| V0.7 | 📋 规划中 | Context Builder（会话、文件、Memory、Knowledge 上下文自动构建） |
| V0.8 | 📋 规划中 | Event Bus（Tool、LLM、Workflow 全事件流） |
| V0.9 | 📋 规划中 | Runtime Stability（Retry、Timeout、Cancellation、Checkpoint、Recovery） |
| V1.0 | 📋 规划中 | Runtime SDK（统一 Agent Runtime API，所有 Agent 共用） |

---

### 第二阶段：Workflow Engine（V1.1 ~ V1.5）

> 目标：从 Agent 演进为 Workflow，实现复杂任务编排。

| 版本 | 状态 | 描述 |
|------|------|------|
| V1.1 | 📋 规划中 | DAG Workflow Engine（节点 + 边） |
| V1.2 | 📋 规划中 | 条件、循环、并行、子流程、动态节点 |
| V1.3 | 📋 规划中 | Human-in-the-loop（人工审批、人工确认、等待输入） |
| V1.4 | 📋 规划中 | Checkpoint & Resume（流程恢复、失败重试、补偿机制） |
| V1.5 | 📋 规划中 | Workflow Designer（可视化拖拽流程设计器） |

---

### 第三阶段：Knowledge Engine（V1.6 ~ V2.0）

> 目标：构建企业级知识引擎，而不仅仅是 RAG。

| 版本 | 状态 | 描述 |
|------|------|------|
| V1.6 | 📋 规划中 | 文档上传、解析（PDF、Word、Excel、PPT、Markdown） |
| V1.7 | 📋 规划中 | OCR、图片理解、表格解析、多模态知识抽取 |
| V1.8 | 📋 规划中 | Hybrid Search（全文 + 向量 + Metadata） |
| V1.9 | 📋 规划中 | ReRank、Citation、Knowledge Cache |
| V2.0 | 📋 规划中 | 长期 Memory + 企业知识库 + Workspace 隔离 |

---

### 第四阶段：Skill Engine（V2.1 ~ V2.5）

> 目标：建立 Tool → Skill → Workflow → Agent 四层能力体系。

| 版本 | 状态 | 描述 |
|------|------|------|
| V2.1 | 📋 规划中 | Skill Runtime（多个 Tool 封装为 Skill） |
| V2.2 | 📋 规划中 | Skill Registry（版本管理、权限、配置） |
| V2.3 | 📋 规划中 | Skill Marketplace（技能市场） |
| V2.4 | 📋 规划中 | 可视化 Skill Builder |
| V2.5 | 📋 规划中 | Skill Sharing & Import/Export |

---

### 第五阶段：Expert Team（V2.6 ~ V3.0）

> 目标：打造 AI 专家团队，让多个 Agent 像真实团队一样协作。

| 版本 | 状态 | 描述 |
|------|------|------|
| V2.6 | 📋 规划中 | Team Runtime（团队执行框架） |
| V2.7 | 📋 规划中 | Team Leader（任务拆解、调度、协调） |
| V2.8 | 📋 规划中 | Expert Roles（架构、Java、Python、DBA、测试、安全等专家） |
| V2.9 | 📋 规划中 | Reviewer / Judge（自动 Review、评分、纠错） |
| V3.0 | 📋 规划中 | Team Builder（自定义专家团队、组织管理） |

---

### 第六阶段：Platform（V3.1 ~ V3.8）

> 目标：打造真正的企业级 Agent Platform。

| 版本 | 状态 | 描述 |
|------|------|------|
| V3.1 | 📋 规划中 | Agent Builder（Agent 可视化配置） |
| V3.2 | 📋 规划中 | Workflow Builder |
| V3.3 | 📋 规划中 | Prompt Builder（Prompt 模板管理） |
| V3.4 | 📋 规划中 | Knowledge Builder |
| V3.5 | 📋 规划中 | Tool Builder |
| V3.6 | 📋 规划中 | Model Router（多模型路由、Fallback、成本优化） |
| V3.7 | 📋 规划中 | Multi Tenant（租户、Workspace、RBAC） |
| V3.8 | 📋 规划中 | 企业控制台（Dashboard、监控、日志、审计） |

---

### 第七阶段：Enterprise（V4.0 ~ V4.5）

> 目标：满足企业生产环境需求。

| 版本 | 状态 | 描述 |
|------|------|------|
| V4.0 | 📋 规划中 | OpenTelemetry + Prometheus + Grafana |
| V4.1 | 📋 规划中 | 审计日志、成本统计、Token Usage |
| V4.2 | 📋 规划中 | Secret Manager、Prompt Security、防 Prompt Injection |
| V4.3 | 📋 规划中 | Rate Limit、Quota、API Key 管理 |
| V4.4 | 📋 规划中 | 熔断、降级、缓存、消息队列 |
| V4.5 | 📋 规划中 | Kubernetes、Horizontal Scaling、多区域部署 |

---

### 第八阶段：AI Ecosystem（V5.0）

> 目标：打造开放生态，支持第三方扩展。

| 版本 | 状态 | 描述 |
|------|------|------|
| V5.0 | 📋 规划中 | MCP Client + MCP Server + A2A Protocol + Plugin SDK + Python SDK + Java SDK + TypeScript SDK + Agent Marketplace + Skill Marketplace + Workflow Marketplace |

---

## 最终平台能力（Vision）

```
Winter Agent Platform

├── Runtime Engine
│   ├── Planner
│   ├── Context Builder
│   ├── Event Bus
│   ├── Executor
│   ├── Memory
│   └── Checkpoint
│
├── Workflow Engine
│   ├── DAG
│   ├── Parallel
│   ├── Loop
│   ├── Condition
│   ├── Human Approval
│   └── Resume
│
├── Knowledge Engine
│   ├── Document Parsing
│   ├── Hybrid Search
│   ├── Multi Modal
│   ├── Long Memory
│   └── Citation
│
├── Skill Engine
│   ├── Tool Registry
│   ├── Skill Registry
│   ├── Skill Builder
│   └── Skill Marketplace
│
├── Expert Team
│   ├── Team Builder
│   ├── Leader
│   ├── Experts
│   ├── Reviewer
│   └── Judge
│
├── Platform
│   ├── Agent Builder
│   ├── Workflow Builder
│   ├── Prompt Builder
│   ├── Knowledge Builder
│   ├── Tool Builder
│   └── Model Router
│
└── Enterprise
    ├── Multi Tenant
    ├── Observability
    ├── Security
    ├── Audit
    ├── Scaling
    └── Open Ecosystem (MCP / A2A / SDK)
```

> **最终目标：Winter Agent 不仅是一个 AI Agent 项目，而是一个面向企业的 AI Agent Platform（AI Agent Operating System），支持 Agent、Workflow、Skill、Knowledge、Expert Team、MCP、A2A、开放生态的完整平台。**
> 详细差距分析参见 [docs/enterprise-gap-analysis.md](docs/enterprise-gap-analysis.md)

## License

MIT
