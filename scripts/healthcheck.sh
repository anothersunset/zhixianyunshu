#!/usr/bin/env bash
# v2-step-32 + polish-9: 检查三服务状态 + MCP/A2A 导出点。
# polish-9 修复: "$url " 等末尾空格 bug, curl 会拼成 URL%20 全 ❌
set -uo pipefail

check() {  # check <name> <url> <pattern>
  local name="$1" url="$2" pat="$3"
  local body
  body=$(curl -fsS --max-time 5 "$url" 2>/dev/null || echo "")
  if [ -n "$body" ] && { [ -z "$pat" ] || echo "$body" | grep -qE "$pat"; }; then
    printf '  \u2705 %-20s %s\n' "$name" "$url"
  else
    printf '  \u274C %-20s %s\n' "$name" "$url"
  fi
}

echo "==> ZhiQian 健康检查"
check "backend health" "http://localhost:8080/actuator/health" "UP"
check "rag health"     "http://localhost:8001/health"          "ok"
check "web"            "http://localhost:5173"                 ""
check "mcp manifest"   "http://localhost:8001/mcp/manifest"    "zhiqian-mcp"
check "a2a card"       "http://localhost:8080/.well-known/agent.json" "sql.transpile"
check "reports/status" "http://localhost:8001/reports/status"  "typst_available"
check "datasets mysql" "http://localhost:8080/actuator/health" "UP"
