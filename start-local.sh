#!/bin/bash
# 本地启动脚本（不依赖 Docker）
# 使用 H2 内存数据库，避免 PostgreSQL 依赖

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo "===== 检查依赖 ====="

# 检查 Python
if ! command -v python &> /dev/null; then
    echo "错误: Python 未安装"
    exit 1
fi
echo "Python: $(python --version)"

# 检查 Java
if ! command -v java &> /dev/null; then
    echo "错误: Java 未安装"
    exit 1
fi
echo "Java: $(java -version 2>&1 | head -1)"

# 检查 Maven（使用 Maven Wrapper）
if [ ! -f "$PROJECT_ROOT/backend/mvnw" ]; then
    echo "生成 Maven Wrapper..."
    cd "$PROJECT_ROOT/backend"
    mvn wrapper:wrapper -Dmaven=3.9.6 2>/dev/null || {
        echo "请手动安装 Maven: https://maven.apache.org/install.html"
        exit 1
    }
    cd "$PROJECT_ROOT"
fi
echo "Maven Wrapper: OK"

echo ""
echo "===== 安装 Python 依赖 ====="
cd "$PROJECT_ROOT/rag"
pip install -r requirements.txt 2>/dev/null || pip install -e . 2>/dev/null || {
    echo "警告: Python 依赖安装失败，尝试继续..."
}
cd "$PROJECT_ROOT"

echo ""
echo "===== 启动服务 ====="

# 1. 启动 RAG 服务（后台）
echo "启动 RAG 服务 (端口 8001)..."
cd "$PROJECT_ROOT/rag"
python -m app.main > /tmp/rag.log 2>&1 &
RAG_PID=$!
echo "RAG PID: $RAG_PID"

# 等待 RAG 服务启动
sleep 5
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "✓ RAG 服务启动成功"
else
    echo "⚠ RAG 服务可能未正常启动，检查 /tmp/rag.log"
fi

# 2. 启动后端（使用 local profile，H2 内存数据库）
echo "启动后端 (端口 8080, profile=local)..."
cd "$PROJECT_ROOT/backend"
export SPRING_PROFILES_ACTIVE=local
./mvnw spring-boot:run > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# 等待后端启动
echo "等待后端启动..."
for i in $(seq 1 60); do
    if curl -s http://localhost:8080/actuator/health > /dev/null 2>&1; then
        echo "✓ 后端启动成功"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "⚠ 后端启动超时，检查 /tmp/backend.log"
    fi
    sleep 2
done

echo ""
echo "===== 服务状态 ====="
echo "RAG:     http://localhost:8001 (PID: $RAG_PID)"
echo "Backend: http://localhost:8080 (PID: $BACKEND_PID)"
echo ""
echo "日志文件:"
echo "  RAG:     /tmp/rag.log"
echo "  Backend: /tmp/backend.log"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
trap "echo '停止服务...'; kill $RAG_PID $BACKEND_PID 2>/dev/null; exit" INT TERM
wait
