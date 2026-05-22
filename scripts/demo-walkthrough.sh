#!/usr/bin/env bash
# v2-step-32 + polish-9: 一键拉起智迁云枢演示栈。
# polish-9 修复: cd "$ROOT " / command -v "$cmd " / [ "${ENABLE_CDC:-0} " 末尾空格 bug
# 后果: 原版 v1.0.0 此脚本 step1 cd 即崩, 整条 demo 链路无法启动
# 使用: bash scripts/demo-walkthrough.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

hr() { echo; echo "==> $*"; echo; }

hr "[1/6] 检查依赖"
for cmd in docker docker-compose curl jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "缺依赖: $cmd"; exit 1; }
done
echo "  docker: $(docker --version)"
echo "  curl  : $(curl --version | head -1)"

hr "[2/6] 拉起公开数据集 MySQL + openGauss"
docker compose -f zhiqian/deploy/datasets/docker-compose.yml --profile datasets up -d
echo "  等待 mysql ready (60s)"
for i in 1 2 3 4 5 6; do
  if docker exec zhiqian-datasets-mysql mysqladmin ping -h localhost -uroot -pzhiqian >/dev/null 2>&1; then break; fi
  sleep 10
done

hr "[3/6] 入 Sakila demo 数据 (可跳, 如已入过)"
if ! docker exec zhiqian-datasets-mysql mysql -uroot -pzhiqian -e "USE sakila; SELECT 1" >/dev/null 2>&1; then
  DATASETS=sakila MYSQL_PORT=33306 bash zhiqian/deploy/datasets/bootstrap.sh
else
  echo "  sakila 已存在, 跳"
fi

hr "[4/6] 拉起 CDC 栈 (可选)"
if [ "${ENABLE_CDC:-0}" = "1" ]; then
  docker compose -f zhiqian/deploy/cdc/docker-compose.yml up -d
  echo "  CDC 启动, Kafka UI 于 :8092"
else
  echo "  CDC 已跳, 设 ENABLE_CDC=1 启用"
fi

hr "[5/6] 启 RAG (后台 8001)"
if ! curl -s http://localhost:8001/health >/dev/null 2>&1; then
  (cd zhiqian/rag && nohup uvicorn app.main:app --port 8001 > /tmp/zhiqian-rag.log 2>&1 &)
  echo "  RAG 启动中, 等待 8001 (~15s)"
  for i in 1 2 3 4 5 6; do
    if curl -s http://localhost:8001/health >/dev/null 2>&1; then break; fi
    sleep 3
  done
fi

hr "[6/6] 启 Backend (8080) + Web (5173)"
if ! curl -s http://localhost:8080/actuator/health >/dev/null 2>&1; then
  (cd zhiqian/backend && nohup ./mvnw spring-boot:run > /tmp/zhiqian-backend.log 2>&1 &)
  echo "  backend 启动中, 等待 8080 (首启 ~60s)"
fi
if ! curl -s http://localhost:5173 >/dev/null 2>&1; then
  (cd zhiqian/web && nohup pnpm dev > /tmp/zhiqian-web.log 2>&1 &)
  echo "  web 启动中, 等待 5173 (~10s)"
fi

hr "完成"
cat <<EOF
  控制台:   http://localhost:5173       (admin / admin123)
  Backend:  http://localhost:8080/swagger-ui.html
  RAG:      http://localhost:8001/docs
  MCP RPC:  http://localhost:8001/mcp/rpc
  A2A card: http://localhost:8080/.well-known/agent.json

  演示模式:   http://localhost:5173/present
  端侧小模:   http://localhost:5173/edge
  PDF 报告:    POST http://localhost:8001/reports/generate

  残渣清除: docker compose -f zhiqian/deploy/datasets/docker-compose.yml --profile datasets down -v
EOF
