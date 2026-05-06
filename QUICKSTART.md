# 快速启动脚本

## 方式一：一键启动所有服务

```bash
./start-dev.sh
```

这会自动启动：
- 前端服务 (http://localhost: 3000)
- 后端服务 (http://localhost: 8080)
- AI 服务 (http://localhost: 8000)

## 方式二：Docker Compose

```bash
# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置 LLM_API_KEY

# 启动所有服务
docker-compose up --build

# 后台运行
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 方式三：分别启动

### 1. 启动 AI 服务

```bash
cd ai_service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export LLM_API_KEY=your-api-key
uvicorn main:app --reload --port 8000
```

### 2. 启动后端服务

```bash
cd backend
./gradlew bootRun
```

### 3. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

## 访问地址

- 前端界面：http://localhost:3000
- 后端 API：http://localhost:8080/api/chat/stream
- AI 服务：http://localhost:8000/health

## 故障排查

### 前端无法连接后端

检查前端代理配置：
```bash
cat frontend/vite.config.ts
```

### 后端无法连接 AI 服务

检查后端配置：
```bash
cat backend/src/main/resources/application.yml
```

### AI 服务报错

检查环境变量：
```bash
echo $LLM_API_KEY
```

### 端口被占用

修改对应服务的端口配置：
- 前端：frontend/vite.config.ts
- 后端：backend/src/main/resources/application.yml
- AI 服务：main.py uvicorn 启动参数

## 依赖检查

启动前确保已安装：
- Node.js 20+
- Python 3.10+
- Java 17+
- Docker & Docker Compose (可选)

```bash
# 检查版本
node -v
python3 --version
java -version
docker --version
docker-compose --version
```
