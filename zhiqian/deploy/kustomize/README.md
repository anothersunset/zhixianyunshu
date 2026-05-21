# ZhiQian YunShu Kustomize 部署

> v2-step-18 交付。Kustomize 是云原生 K8s 原生支持的部署方案 (kubectl 1.14+ 内置), 相较 Helm 更轻量, 不需渲染步骤, ArgoCD 原生消费。

## 目录结构

```
kustomize/
  base/                     # 生产可用的基准清单
    kustomization.yaml      # 资源联合 + secretGenerator + image 钉捆
    namespace.yaml          # zhiqian 命名空间
    postgres-*.yaml         # PostgreSQL 16 StatefulSet (10Gi PVC)
    backend-*.yaml          # Spring Boot Deployment + ConfigMap + Service
    rag-*.yaml              # FastAPI Deployment + Service
    web-*.yaml              # Vue 3 + nginx Deployment + Service
  overlays/
    dev/                    # 开发: 1 副本, 低内存, NodePort
    prod/                   # 生产: 2+ 副本, 严资源, Ingress
```

## 快速启动

```bash
# 1) 检查 manifest (不应用)
kubectl kustomize zhiqian/deploy/kustomize/base | less

# 2) dev 环境一键部署
kubectl apply -k zhiqian/deploy/kustomize/overlays/dev

# 3) 生产 (记得先 patch 真 secret)
kubectl apply -k zhiqian/deploy/kustomize/overlays/prod

# 4) 查看
kubectl -n zhiqian get all
kubectl -n zhiqian logs deploy/zhiqian-backend -f
```

## 重要 secret 覆盖

默认 `secretGenerator` 走占位值, **生产必须覆盖**:

```bash
# 方案 A: 环境变量 patch (overlays/prod/secret-patch.yaml)
# 方案 B: External Secrets Operator + Vault
# 方案 C: Sealed Secrets (加密后提交 git)
```

需覆盖的 key:
- `jwt-secret` (≥ 32 字符随机)
- `deepseek-api-key` (sk-xxx)
- `langfuse-public-key` / `langfuse-secret-key` (可选)
- `postgres-password`

## Helm 备注

`deploy/helm/` 目录保留但已 deprecated, 原因: 文件推送代理不能保留原始 Helm `{` `{` `}` `}` 模板语法。Kustomize 纯 YAML 路径本就是 #19 ArgoCD 的首选交付格式。如贴要 Helm, 后续可用 `kompose` 或手工转换。
