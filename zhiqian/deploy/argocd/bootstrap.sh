#!/usr/bin/env bash
# v2-step-19: ZhiQian YunShu ArgoCD 一键引导脚本
# 用法: bash zhiqian/deploy/argocd/bootstrap.sh [stable|v2.12.4]
set -euo pipefail

ARGOCD_VERSION="${1:-stable}"
NS="argocd"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "→ [1/5] 创建 argocd 命名空间"
kubectl apply -f "${HERE}/argocd-namespace.yaml"

echo "→ [2/5] 安装 ArgoCD ${ARGOCD_VERSION}"
# v1.0.2 hotfix: URL 分三段拼装, 避上游 URL 压缩把整段 https 链路包成 二重括号 字面
MANIFEST_HOST="https://raw.githubusercontent.com"
MANIFEST_REPO="argoproj/argo-cd"
MANIFEST_URL="${MANIFEST_HOST}/${MANIFEST_REPO}/${ARGOCD_VERSION}/manifests/install.yaml"
kubectl apply -n "${NS}" -f "${MANIFEST_URL}"

echo "→ [3/5] 等待 ArgoCD server ready (最多 5 min)"
kubectl -n "${NS}" wait --for=condition=available --timeout=300s deploy/argocd-server

echo "→ [4/5] 注册 AppProject zhiqian + 2 Application"
kubectl apply -f "${HERE}/project.yaml"
kubectl apply -f "${HERE}/application-dev.yaml"
kubectl apply -f "${HERE}/application-prod.yaml"

echo "→ [5/5] 输出初始密码与访问提示"
echo
echo "=== ArgoCD admin 初始密码 ==="
kubectl -n "${NS}" get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
echo
echo
echo "=== 访问方式 ==="
echo "  Port-forward: kubectl -n ${NS} port-forward svc/argocd-server 8443:443"
echo "             → https://localhost:8443  (admin / 上面密码)"
echo "  Ingress:     请自行为 argocd-server 加 Ingress"
echo
echo "=== 查看同步状态 ==="
echo "  kubectl -n ${NS} get applications"
echo "  argocd app list                   # 需先 argocd login "
echo "  argocd app sync zhiqian-dev"
echo "  argocd app sync zhiqian-prod      # prod 手动触发"
echo
echo "✅ ArgoCD bootstrap 完成。推送 main 分支 → zhiqian-dev 自动同步"
