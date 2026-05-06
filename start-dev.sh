#!/bin/bash

echo "🚀 启动 AI Chat V0.2 开发环境..."
echo ""

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ 错误：未找到 Node.js，请先安装 Node.js 20+"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误：未找到 Python 3.10+"
    exit 1
fi

# 检查 Java
if ! command -v java &> /dev/null; then
    echo "❌ 错误：未找到 Java 21+"
    exit 1
fi

# 检查 Maven
if ! command -v mvn &> /dev/null; then
    echo "❌ 错误：未找到 Maven (mvn)，请先安装"
    exit 1
fi

echo "✅ 环境检查通过"
echo ""

# 启动 AI 服务
echo "📦 启动 AI 服务 (端口 8000)..."
cd ai_service
if [ ! -d "venv" ]; then
    echo "创建 Python 虚拟环境..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

if [ -z "$API_KEY" ]; then
    echo "⚠️  警告：API_KEY 未设置，请确认已在 .env 中配置以启用大模型"
fi
if [ -z "$POSTGRES_URI" ]; then
    echo "⚠️  注意：未探测到 POSTGRES_URI，请确保 AI 服务能连接到默认或配置的 DB"
fi

uvicorn main:app --reload --port 8000 &
AI_PID=$!
cd ..
echo "✅ AI 服务已启动 (PID: $AI_PID)"
echo ""

# 启动后端服务
echo "📦 启动后端服务 (端口 8080)..."
cd backend
mvn spring-boot:run &
BACKEND_PID=$!
cd ..
echo "✅ 后端服务已启动 (PID: $BACKEND_PID)"
echo ""

# 启动前端服务
echo "📦 启动前端服务 (端口 3000)..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!
cd ..
echo "✅ 前端服务已启动 (PID: $FRONTEND_PID)"
echo ""

echo "============================================"
echo "🎉 所有服务已启动!"
echo ""
echo "前端服务：http://localhost:3000"
echo "后端服务：http://localhost:8080"
echo "AI 服务：   http://localhost:8000"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "============================================"

# 等待中断信号
trap "kill $AI_PID $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM EXIT

wait
