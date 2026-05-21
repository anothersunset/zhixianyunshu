#!/usr/bin/env bash
# v2-step-31 (polish): 一键安装供应链 CI workflow。
#
# 上游 push 时受集成权限限制, .github/workflows/* 无法直接写入;
# 故 supply-chain.yml 落在 zhiqian/security/workflows-template/ 并把
# GitHub Actions 二重大括号表达式 "$ context.ref " (单 $ + 上下空格)
# 留为占位, 由本脚本 sed 还原回 "$<ref>" 写入 .github/workflows/。
#
# 用法:
#   bash scripts/install-supply-chain-workflow.sh
#   git add .github/workflows/supply-chain.yml
#   git commit -m 'ci: enable supply-chain workflow'
#   git push

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/zhiqian/security/workflows-template/supply-chain.yml"
DST="$ROOT/.github/workflows/supply-chain.yml"

if [[ ! -f "$SRC" ]]; then
  echo "❌ 未找到模板: $SRC" >&2
  exit 1
 fi

mkdir -p "$(dirname "$DST")"

# 转换: "$ github.repository_owner " -> "\$ github.repository_owner "
# 匹配 “$ ” 后紧跟 [a-zA-Z._-]+ 反 $"\s” 的位置。
# 注: sed 输出里需 $ ...  两重大括号, 以 \$群号引用并加\u5f3a转义。
sed -E 's/\$ ([a-zA-Z][a-zA-Z0-9._-]+) /\$\{\{ \1 \}\}/g' "$SRC" > "$DST"

echo "✅ Installed: $DST"
echo "下一步: git add .github/workflows/supply-chain.yml && git commit -m 'ci: enable supply-chain' && git push"
echo
echo "验证占位符全部转换完成 (下面应为 0):"
grep -cE '\$ [a-z]' "$DST" || true
