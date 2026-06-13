#!/bin/bash
# RAG 服务稳定启动脚本
# 功能：启动 RAG 服务 + 看门狗，确保服务持续运行

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 默认配置
RAG_PORT=${RAG_PORT:-8004}
MEMORY_LIMIT=${RAG_MEMORY_LIMIT_MB:-4500}

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARN:${NC} $1"; }
err() { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $1"; }

# 检查端口是否被占用
check_port() {
    if netstat -ano 2>/dev/null | grep -q ":${RAG_PORT}.*LISTEN"; then
        return 0  # 端口被占用
    fi
    return 1
}

# 杀掉占用端口的进程
kill_port_process() {
    local pid
    pid=$(netstat -ano 2>/dev/null | grep ":${RAG_PORT}.*LISTEN" | awk '{print $5}' | head -1)
    if [ -n "$pid" ] && [ "$pid" != "0" ]; then
        warn "终止占用端口 $RAG_PORT 的进程 PID=$pid"
        taskkill //F //PID "$pid" 2>/dev/null || true
        sleep 2
    fi
}

# 启动 RAG 服务
start_rag() {
    log "启动 RAG 服务 (端口=$RAG_PORT, 内存限制=${MEMORY_LIMIT}MB)..."

    export HF_HUB_OFFLINE=1
    export RAG_USE_RERANKER=true
    export RAG_RRF_K=15
    export RAG_RRF_CHANNEL_WEIGHTS="1.0,1.0,0.5"
    export RAG_QDRANT_URL=http://localhost:6333
    export RAG_MEMORY_LIMIT_MB=$MEMORY_LIMIT

    # 后台启动，日志写入文件
    nohup python -m uvicorn app.main:app \
        --port "$RAG_PORT" \
        --host 0.0.0.0 \
        --log-level info \
        --timeout-keep-alive 300 \
        > rag_service.log 2>&1 &

    local rag_pid=$!
    echo "$rag_pid" > .rag.pid
    log "RAG 服务已启动 PID=$rag_pid"

    # 等待就绪
    log "等待 RAG 服务就绪..."
    for i in $(seq 1 60); do
        if curl -s "http://127.0.0.1:${RAG_PORT}/health" > /dev/null 2>&1; then
            log "RAG 服务就绪! (${i}x3s)"
            return 0
        fi
        sleep 3
    done
    err "RAG 服务 180s 内未就绪!"
    return 1
}

# 启动看门狗
start_watchdog() {
    log "启动看门狗..."
    nohup python rag_watchdog.py > /dev/null 2>&1 &
    local wd_pid=$!
    log "看门狗已启动 PID=$wd_pid"
}

# 主流程
main() {
    log "=== RAG 服务稳定启动 ==="

    # 1. 检查并清理端口
    if check_port; then
        warn "端口 $RAG_PORT 已被占用"
        kill_port_process
    fi

    # 2. 启动 RAG 服务
    if ! start_rag; then
        err "RAG 服务启动失败!"
        exit 1
    fi

    # 3. 启动看门狗
    start_watchdog

    log "=== 启动完成 ==="
    log "RAG 服务: http://127.0.0.1:$RAG_PORT"
    log "日志文件: $SCRIPT_DIR/rag_service.log"
    log "看门狗日志: $SCRIPT_DIR/rag_watchdog.log"
    log "停止命令: python rag_watchdog.py --stop"
}

main "$@"
