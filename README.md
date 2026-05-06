# AI Chat V0.2

智能对话系统原型，实现前端 - 后端 - AI 服务的全链路流式对话与历史会话能力。

## 技术栈

- **前端**: React 18 + Vite + TypeScript + Tailwind CSS
- **后端**: Spring Boot 3 + WebFlux + Java + Maven
- **AI 服务**: Python + FastAPI + LangChain + LangGraph + PostgreSQL Checkpointer

## 快速开始

### 方式一：Docker Compose (推荐)

1. 配置环境变量:
```bash
cp .env.example .env
# 编辑 .env 文件，设置 API_KEY、BASE_URL、MODEL
```

2. 启动所有服务:
```bash
docker-compose up --build
```

3. 访问前端：http://localhost:3000

### 方式三：一键启动脚本

```bash
# 设置环境变量
export API_KEY=your-api-key
export BASE_URL=https://api.openai.com/v1
export MODEL=gpt-4

# 启动所有服务（前端、后端、AI 服务）
./start-dev.sh
```

服务会自动启动在：
- 前端：http://localhost:3000
- 后端：http://localhost:8080
- AI 服务：http://localhost:8000

### 方式二：本地分别启动

#### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

#### 后端

```bash
cd backend
mvn spring-boot:run
```

服务运行在 http://localhost:8080

#### AI 服务

```bash
cd ai_service
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 设置环境变量（任选一种）
export API_KEY=your-api-key
# 或使用 .env 文件：cp .env.example .env 并编辑

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

服务运行在 http://localhost:8000

## 环境变量

### AI 服务核心配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| API_KEY | LLM API 密钥 | 空 |
| BASE_URL | LLM API 基础 URL | https://api.openai.com/v1 |
| MODEL | 模型名称 | gpt-3.5-turbo |
| POSTGRES_URI | LangGraph 持久化数据库连接串 | postgresql://postgres:postgres@localhost:5432/aichat |

### LangSmith（可选）

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| LANGCHAIN_API_KEY | LangSmith API Key | 空 |
| LANGCHAIN_PROJECT | 追踪项目名 | default |
| LANGCHAIN_ENDPOINT | LangSmith 地址 | https://api.smith.langchain.com |

## API 接口

### POST `/api/chat/stream`

流式对话接口（SSE）

**请求**:
```json
{
  "message": "你好",
  "conversationId": "optional-uuid"
}
```

### GET `/api/chat/history/{conversationId}`

查询指定会话历史（后端透传 AI 服务返回值）

**响应**:
```json
{
  "messages": [
    { "role": "user", "content": "你好" },
    { "role": "assistant", "content": "你好，我是 AI 助手。" }
  ]
}
```

## 功能特性

- ✅ 流式对话（打字机效果）
- ✅ Markdown 渲染
- ✅ 代码高亮
- ✅ 自动滚动
- ✅ 错误处理
- ✅ 响应式设计
- ✅ 多轮对话历史记忆（PostgreSQL + LangGraph）
- ✅ 本地历史会话侧边栏列表
- ✅ 代码块自动深浅色语法高亮与“一键复制”
- ✅ LangSmith 全链路观测追踪

## 项目结构

```
.
├── frontend/           # React 前端
│   ├── src/
│   │   ├── components/ # ChatInput, ChatMessage, Sidebar等
│   │   ├── hooks/      # useChat, useSessions等
│   │   ├── services/   # 流式与历史API抓取
│   │   └── types/
│   └── ...
├── backend/            # Spring Boot 后端 (BFF 代理)
│   └── src/main/java/com/example/aichat/
│       ├── controller/ # 暴露流式调用和历史聊天记录查询接口
│       ├── service/    # 非阻塞式跨服务 HTTP 请求
│       └── ...
├── ai_service/         # Python AI 服务 (LangGraph 核心大脑)
│   ├── graph/
│   │   ├── state.py    # 图流转结构状态
│   │   ├── nodes.py    # 思考和决策节点
│   │   └── graph.py    # 构建拓扑图、引入 PostgresSaver
│   ├── config.py       # 环境变量与LangSmith挂载
│   └── main.py         # HTTP端点及 PostgreSQL 连接池生命周期
└── docker-compose.yml
```

## 开发计划

- [x] V0.1: 基础对话与流式框架
- [x] V0.2: 多轮对话历史管理沉淀（PostgreSQL + Sidebar）
- [ ] V0.3: 多工具集成（搜索、数据库查询）
- [ ] V0.4: 用户认证和权限
- [ ] V0.5: 多模型切换

## License

MIT
