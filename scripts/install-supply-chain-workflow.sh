#!/usr/bin/env bash
# v2-step-31 (polish-10): 一键安装 CI + 供应链 workflow。
#
# 上游 push 时受集成权限限制, .github/workflows/* 无法直接写入;
# 故 ci.yml + supply-chain.yml 落在 zhiqian/security/workflows-template/ 并把
# GitHub Actions 二重括号表达式 ("$ context.ref " 单 $ + 上下空格) 留为占位,
# 由本脚本 sed 还原后写入 .github/workflows/。
#
# 用法:
#   bash scripts/install-supply-chain-workflow.sh
#   git add .github/workflows/
#   git commit -m 'ci: install workflows from templates'
#   git push

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TPL_DIR="$ROOT/zhiqian/security/workflows-template"
DST_DIR="$ROOT/.github/workflows"
mkdir -p "$DST_DIR"

# 不在源码字面书写裸 二重括号 (上游 URL 压缩会吃掉), 改为运行时拼装。
LBR='{'
RBR='}'
HASHFILES_REPL="\$${LBR}${LBR} hashFiles('**/pom.xml') ${RBR}${RBR}"

restore() {
  local src="$1" dst="$2"
  # 通用占位还原:  "$ name " (单 $ + 空格界定) → 二重括号表达式
  sed -E 's/\$ ([a-zA-Z][a-zA-Z0-9._-]+) /\$\{\{ \1 \}\}/g' "$src" \
    | sed "s|POM_XML_HASH|${HASHFILES_REPL}|g" > "$dst"
  echo "✅ $dst"
}

for name in ci supply-chain; do
  SRC="$TPL_DIR/$name.yml"
  DST="$DST_DIR/$name.yml"
  if [[ -f "$SRC" ]]; then
    restore "$SRC" "$DST"
  else
    echo "⚠️ 模板缺失: $SRC, 跳过"
  fi
done

echo
echo "下一步: git add .github/workflows/ && git commit -m 'ci: install workflows' && git push"
echo
echo "验证占位符全部转换 (下面所有 yml 文件应全为 0):"
for f in "$DST_DIR"/*.yml; do
  echo -n "  $f: "
  grep -cE '\$ [a-z]|POM_XML_HASH' "$f" || true
done
