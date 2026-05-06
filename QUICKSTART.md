# 快速启动

## 方式一：一键启动所有服务

```bash
./start-dev.sh
```

这会自动启动：
- 前端服务 (http://localhost:3000)
- 后端服务 (http://localhost:8080)
- AI 服务 (http://localhost:8000)

## 方式二：Docker Compose

```bash
cp .env.example .env
# 编辑 .env，至少设置 API_KEY 和 POSTGRES_URI

docker-compose up --build
```

## 方式三：分别启动

### 0. 准备 PostgreSQL 数据库
```bash
docker run -d --name local-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15
```

### 1. 启动 AI 服务

```bash
cd ai_service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置环境变量示例
export API_KEY=your-api-key
export BASE_URL=https://api.openai.com/v1
export MODEL=gpt-4o-mini
export POSTGRES_URI=postgresql://postgres:postgres@localhost:5432/aichat
# 可选 LangSmith
# export LANGCHAIN_API_KEY=ls__xxx
# export LANGCHAIN_PROJECT=winter-agent

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动后端服务（Maven）

```bash
cd backend
mvn spring-boot:run
```

### 3. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

## 访问地址

- 前端界面：http://localhost:3000
- 后端流式接口：http://localhost:8080/api/chat/stream
- 后端历史接口：http://localhost:8080/api/chat/history/{conversationId}
- AI 服务健康检查：http://localhost:8000/health

## 故障排查

### 前端无法连接后端
```bash
cat frontend/vite.config.ts
```

### 后端无法连接 AI 服务
```bash
cat backend/src/main/resources/application.yml
```

### AI 服务报错
```bash
cd ai_service
python -c "from config import settings; print(settings.api_key != '', settings.postgres_uri)"
```

### 端口被占用
- 前端：`frontend/vite.config.ts`
- 后端：`backend/src/main/resources/application.yml`
- AI 服务：`uvicorn` 启动参数

## 依赖检查

- Node.js 20+
- Python 3.10+
- Java 21+
- Maven 3.9+
- Docker & Docker Compose (可选)

```bash
node -v
python3 --version
java -version
mvn -v
docker --version
docker-compose --version
```
