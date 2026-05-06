# AI Chat V0.1

智能对话系统原型，实现前端 - 后端-AI 服务的全链路流式对话功能。

## 技术栈

- **前端**: React 18 + Vite + TypeScript + Tailwind CSS
- **后端**: Spring Boot 3 + WebFlux + Kotlin
- **AI 服务**: Python + FastAPI + LangGraph

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
./gradlew bootRun
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

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| API_KEY | LLM API 密钥（优先使用） | 空 |
| BASE_URL | LLM API 基础 URL（优先使用） | https://api.openai.com/v1 |
| MODEL | 模型名称（优先使用） | gpt-3.5-turbo |
| LLM_API_KEY | LLM API 密钥（兼容旧配置） | 空 |
| LLM_BASE_URL | LLM API 基础 URL（兼容旧配置） | https://api.openai.com/v1 |
| MODEL_NAME | 模型名称（兼容旧配置） | gpt-3.5-turbo |

## API 接口

### POST /api/chat/stream

流式对话接口

**请求**:
```json
{
  "message": "你好",
  "conversationId": "optional-uuid"
}
```

**响应** (SSE):
```
event: token
data: {"content": "你"}

event: token
data: {"content": "好"}

event: done
data: {}
```

## 功能特性

- ✅ 流式对话（打字机效果）
- ✅ Markdown 渲染
- ✅ 代码高亮
- ✅ 自动滚动
- ✅ 错误处理
- ✅ 响应式设计

## 项目结构

```
.
├── frontend/           # React 前端
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── types/
│   └── ...
├── backend/            # Spring Boot 后端
│   └── src/main/kotlin/com/example/aichat/
│       ├── controller/
│       ├── service/
│       ├── client/
│       └── model/
├── ai_service/         # Python AI 服务
│   ├── graph/
│   │   ├── state.py
│   │   ├── nodes.py
│   │   └── graph.py
│   └── main.py
└── docker-compose.yml
```

## 开发计划

- [ ] V0.2: 对话历史管理
- [ ] V0.3: 多工具集成（搜索、数据库查询）
- [ ] V0.4: 用户认证和权限
- [ ] V0.5: 多模型切换

## License

MIT
