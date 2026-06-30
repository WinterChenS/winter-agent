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

| 版本 | 状态 | 描述 |
|------|------|------|
| V0.1 | ✅ 完成 | 基础对话 + 流式框架 |
| V0.2 | ✅ 完成 | 多轮会话历史 + LangSmith 观测 |
| V0.3 | 🚧 进行中 | 工具调用运行时 (ReAct · 工具注册表 · 策略门控) |
| V0.4 | 🚧 进行中 | 多智能体路由 + 协作编排 |
| V0.5 | 🚧 进行中 | 计划-执行-合成流水线 |
| V0.6 | 📋 规划中 | 反思系统 (自我纠正 · 评审智能体 · 重试循环) |
| V0.7 | 📋 规划中 | 人在回路中 (审批流程 · 暂停/恢复) |
| V1.0 | 📋 规划中 | Agent 市场 · 工具市场 · 团队协作 · 长期记忆 |
| V2.0 | 📋 规划中 | MCP · A2A · 分布式智能体 |

## License

MIT
