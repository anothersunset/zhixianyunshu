#!/usr/bin/env bash
# v2-step-29: 调 ZhiQian API 为 3 个公开表库一个一个迁, 输出表量/耗时。
set -euo pipefail
API="${API:-http://localhost:8080}"
TOKEN="${TOKEN:-}"
AUTH=()
[ -n "$TOKEN" ] && AUTH=(-H "Authorization: Bearer $TOKEN")

for ds in sakila chinook employees; do
  echo "==> migrate $ds"
  curl -s "${AUTH[@]}" -X POST "$API/api/projects" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"benchmark-$ds\",\"sourceDialect\":\"mysql\",\"targetDialect\":\"opengauss\"}" | jq .
  start=$(date +%s)
  curl -s "${AUTH[@]}" -X POST "$API/api/migration/run" \
    -H 'Content-Type: application/json' \
    -d "{\"projectName\":\"benchmark-$ds\",\"sourceDb\":\"$ds\"}" | jq .
  end=$(date +%s)
  echo "   elapsed: $((end - start))s"
done

echo "==> bench summary done"
