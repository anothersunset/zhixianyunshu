#!/usr/bin/env bash
# v2: 加固版三路冒烟检 — 静态 + 轻量运行时验证。
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
warn() { echo -e "  ${DIM}$1${NC}"; }
step() { echo -e "\n${DIM}─── $1${NC}"; }

# ──────────────────────────────────────────────
# 1/3  web (Vue 3 + TS) — 类型检查
# ──────────────────────────────────────────────
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
    echo "  装依赖…"
    if command -v pnpm >/dev/null 2>&1; then pnpm install --frozen-lockfile || pnpm install; else npm install; fi
  fi
  echo "  vue-tsc 类型检查…"
  if command -v pnpm >/dev/null 2>&1; then pnpm exec vue-tsc --noEmit; else npx vue-tsc --noEmit; fi
  pass "web 类型检通过"
  cd "$ROOT"
fi

# ──────────────────────────────────────────────
# 2/3  rag (Python FastAPI) — compile + lint + import chain
# ──────────────────────────────────────────────
step "2/3  rag (Python FastAPI)"
if [[ "${SMOKE_SKIP_RAG:-0}" == "1" ]]; then
  echo "  skipped (SMOKE_SKIP_RAG=1)"
else
  if [[ ! -d zhiqian/rag ]]; then fail "未找到 zhiqian/rag"; fi
  PYTHON=python3
  if ! command -v python3 >/dev/null 2>&1; then
    if command -v python >/dev/null 2>&1; then PYTHON=python; else fail "需 python3"; fi
  fi

  # 2a: 静态编译检查
  echo "  compileall 语法检查…"
  $PYTHON -m compileall -q zhiqian/rag/app
  pass "rag 语法检查通过"

  # 2b: ruff lint (比 pyflakes 更全面)
  if command -v ruff >/dev/null 2>&1; then
    echo "  ruff lint…"
    ruff check zhiqian/rag/app --select E,F,W --ignore E501 --quiet 2>/dev/null || warn "(ruff warnings 不阻断)"
  elif command -v pyflakes >/dev/null 2>&1; then
    echo "  pyflakes lint…"
    pyflakes zhiqian/rag/app || warn "(pyflakes warnings 不阻断)"
  else
    warn "ruff/pyflakes 均未装, 跳过 lint"
  fi

  # 2c: import chain 验证 — 确认依赖可解析、模块可导入
  echo "  import chain 验证…"
  cd zhiqian/rag
  $PYTHON -c "
import sys, importlib
modules = ['app.main', 'app.api.health', 'app.pipelines.retriever']
failed = []
for m in modules:
    try:
        importlib.import_module(m)
    except Exception as e:
        failed.append(f'{m}: {e}')
if failed:
    print('Import failures:', file=sys.stderr)
    for f in failed:
        print(f'  {f}', file=sys.stderr)
    sys.exit(1)
print('  import chain OK: ' + ', '.join(modules))
" 2>&1 || fail "rag import chain 失败 — 依赖未安装或模块有误"
  pass "rag import chain 通过"
  cd "$ROOT"
fi

# ──────────────────────────────────────────────
# 3/3  backend (Maven) — compile + 单元测试
# ──────────────────────────────────────────────
step "3/3  backend (Maven)"
if [[ "${SMOKE_SKIP_BACKEND:-0}" == "1" ]]; then
  echo "  skipped (SMOKE_SKIP_BACKEND=1)"
else
  if [[ ! -d zhiqian/backend ]]; then fail "未找到 zhiqian/backend"; fi
  cd zhiqian/backend
  if [[ -f mvnw ]]; then MVN="./mvnw -q"; elif command -v mvn >/dev/null 2>&1; then MVN="mvn -q"; else fail "需 mvnw 或 mvn"; fi

  # 3a: 编译
  echo "  $MVN -DskipTests compile…"
  $MVN -DskipTests compile
  pass "backend compile 通过"

  # 3b: 跑非集成测试 (排除需要数据库/容器的测试)
  echo "  $MVN test (排除集成测试)…"
  $MVN test -Dtest='!*Integration*,!*Postgres*,!*ApplicationTests' \
      -DfailIfNoTests=false \
      -Dsurefire.useFile=false \
      -q 2>&1 | tail -5
  pass "backend 单元测试通过"
  cd "$ROOT"
fi

echo -e "\n${GREEN}✅ Smoke test 全部通过${NC}\n"
