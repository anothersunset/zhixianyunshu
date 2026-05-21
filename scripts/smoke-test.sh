#!/usr/bin/env bash
# Polish: 三路静态检 — 不启服务, 仅验证可编译 / 可解析。
# 适用 CI fast-feedback gate 或本地提交前快检。
#
# 用法:
#   bash scripts/smoke-test.sh           # 全项
#   SMOKE_SKIP_WEB=1 bash scripts/smoke-test.sh
#   SMOKE_SKIP_RAG=1 bash scripts/smoke-test.sh
#   SMOKE_SKIP_BACKEND=1 bash scripts/smoke-test.sh

set -eo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GREEN="\033[32m"
RED="\033[31m"
DIM="\033[2m"
NC="\033[0m"

pass() { echo -e " ${GREEN}✔${NC} $1"; }
fail() { echo -e " ${RED}✖${NC} $1"; exit 1; }
step() { echo -e "\n${DIM}─── $1${NC}"; }

step "1/3  web (Vue 3 + TS)"
if [[ "${SMOKE_SKIP_WEB:-0}" == "1" ]]; then
  echo "  skipped (SMOKE_SKIP_WEB=1)"
else
  if [[ ! -d zhiqian/web ]]; then fail "未找到 zhiqian/web"; fi
  if ! command -v pnpm >/dev/null 2>&1 && ! command -v npm >/dev/null 2>&1; then
    fail "需 pnpm 或 npm"
  fi
  cd zhiqian/web
  if [[ ! -d node_modules ]]; then
    echo "  装依 (pnpm install --frozen-lockfile)…"
    if command -v pnpm >/dev/null 2>&1; then pnpm install --frozen-lockfile || pnpm install; else npm install; fi
  fi
  echo "  vue-tsc 类型检查…"
  if command -v pnpm >/dev/null 2>&1; then pnpm exec vue-tsc --noEmit; else npx vue-tsc --noEmit; fi
  pass "web 类型检通过"
  cd "$ROOT"
fi

step "2/3  rag (Python FastAPI)"
if [[ "${SMOKE_SKIP_RAG:-0}" == "1" ]]; then
  echo "  skipped (SMOKE_SKIP_RAG=1)"
else
  if [[ ! -d zhiqian/rag ]]; then fail "未找到 zhiqian/rag"; fi
  if ! command -v python3 >/dev/null 2>&1; then fail "需 python3"; fi
  # 只静态 compile, 不安依
  python3 -m compileall -q zhiqian/rag/app
  pass "rag py compile 通过"
  if command -v pyflakes >/dev/null 2>&1; then
    pyflakes zhiqian/rag/app || echo "  ${DIM}(pyflakes warnings ignored)${NC}"
  else
    echo "  ${DIM}pyflakes 未装, 跳过 lint${NC}"
  fi
fi

step "3/3  backend (Maven)"
if [[ "${SMOKE_SKIP_BACKEND:-0}" == "1" ]]; then
  echo "  skipped (SMOKE_SKIP_BACKEND=1)"
else
  if [[ ! -d zhiqian/backend ]]; then fail "未找到 zhiqian/backend"; fi
  cd zhiqian/backend
  if [[ -f mvnw ]]; then MVN="./mvnw -q"; elif command -v mvn >/dev/null 2>&1; then MVN="mvn -q"; else fail "需 mvnw 或 mvn"; fi
  echo "  $MVN -DskipTests compile…"
  $MVN -DskipTests compile
  pass "backend compile 通过"
  cd "$ROOT"
fi

echo -e "\n${GREEN}✅ Smoke test 全部通过${NC}\n"
