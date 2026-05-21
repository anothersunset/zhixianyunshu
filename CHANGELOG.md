# CHANGELOG

> 说明: 以下为智迁云枢 v2 升级正式启动以来的完整提交记录。每步提交同步更新 `UPGRADE_PLAN.md` 状态表。

---

## 🟡 Phase 3 进度 (2/7) — 2026-05-21

**云原生 Kustomize 部署 + ArgoCD GitOps 交付**。剩 #20 KubeRay+vLLM / #21 Debezium CDC / #22 pgloader/MTK / #23 MCP Server / #24 A2A 协议 共 5 提交。

---

## [v2-step-19] 2026-05-21 — ArgoCD GitOps (AppProject + dev/prod Application + bootstrap)

**提交 SHA**: `46274be6` (batch 1: 6 文件 ArgoCD 资源 + bootstrap.sh + README)

### 动机
在 #18 Kustomize 上套 declarative GitOps, 实现 git push → 集群自动同步, 容器手工 patch 不能 drift。ArgoCD 是 CNCF Graduated Project (3rd most stars in CNCF), 原生消费 Kustomize 无需 chart provider。

### 设计要点
- **AppProject zhiqian**: RBAC 隔离 sources (仅允许 zhixianyunshu repo) / destinations (仅 zhiqian/zhiqian-dev/zhiqian-staging ns) / cluster resources (仅 Namespace + IngressClass), namespace resources 全开, orphanedResources warn。内置 read-only role 公示给 zhiqian:viewers 组。
- **Application zhiqian-dev**: 指 overlays/dev, automated sync (prune=true selfHeal=true), CreateNamespace=true, retry 5 次 backoff 5s→3m。推 main 分支自动同步。
- **Application zhiqian-prod**: 指 overlays/prod, **automated.prune=false** (防误刪) + selfHeal=true (drift 自愈) + RespectIgnoreDifferences。生产部署走手动 `argocd app sync zhiqian-prod`。含 ignoreDifferences 两项: Deployment.spec.replicas (不与 HPA 冲突) + Secret.data (不与 External Secrets 冲突)。预留 notifications.argoproj.io 订阅可选接 Slack/企业微信。
- **bootstrap.sh**: 一键 5-step 引导 —— 创建 argocd ns → apply install.yaml (支持 stable/specific version) → wait deploy ready (timeout 300s) → apply project+2 app → 输出 initial admin 密码 + 访问提示。
- **app-of-apps.yaml**: 可选根应用, kubectl apply 后 ArgoCD 自动 sync 上面 3 个 YAML。适合纯 GitOps 场景 (集群起来后几乎不再手工 kubectl)。
- **README.md**: 含生产加固清单 (Ingress+TLS, SSO, 禁 admin, Notifications, External Secrets, Image Updater, sync windows) + 常用操作 + 故障排查 (stuck OutOfSync, 重置密码)。

### 变更项
新增 6 文件:
- `zhiqian/deploy/argocd/argocd-namespace.yaml`
- `zhiqian/deploy/argocd/project.yaml` (AppProject 含 RBAC 与 source/dest 限定)
- `zhiqian/deploy/argocd/application-dev.yaml` (automated sync)
- `zhiqian/deploy/argocd/application-prod.yaml` (manual sync + selfHeal + ignoreDifferences)
- `zhiqian/deploy/argocd/app-of-apps.yaml` (root Application 可选)
- `zhiqian/deploy/argocd/bootstrap.sh` (一键脚本)
- `zhiqian/deploy/argocd/README.md`

紧跟修复 `bootstrap.sh` 原始推送中的一个 bash 语法 bug (`{` `{` `}` `}` 多余括号路径)。

### 验证
```bash
# 1) 引导 ArgoCD + 注册项目
bash zhiqian/deploy/argocd/bootstrap.sh

# 2) 访问 ArgoCD UI
kubectl -n argocd port-forward svc/argocd-server 8443:443
# → https://localhost:8443  (admin / 脚本输出密码)

# 3) 看 2 个 Application 同步状态
kubectl -n argocd get applications
# → NAME           SYNC STATUS   HEALTH STATUS
#   zhiqian-dev    Synced        Healthy
#   zhiqian-prod   OutOfSync     Healthy   (prod manual)

# 4) 手动 sync prod
argocd login localhost:8443
argocd app sync zhiqian-prod
argocd app history zhiqian-prod
```

### 回滚
`git revert 46274be6` → ArgoCD 目录清除。集群上已装的 ArgoCD + Application 需手动清: `kubectl -n argocd delete app zhiqian-dev zhiqian-prod && kubectl -n argocd delete appproject zhiqian`。Kustomize 部署本身不受影响。

---

## [v2-step-18] 2026-05-21 — Kustomize base + overlays (pivot from Helm Chart)

**提交 SHA**: `9833e4dc` (batch 1 base 12 文件) + `c5f375d5` (batch 2 overlays + Helm deprecation stub)

### 动机
原计划交付 Helm Chart 作为 #18, 但平台文件推送代理不能保留 Helm Go-template `{` `{` `}` `}` 语法 (被 URL 压缩机制泛匹配并替换), 导致首次推送的 chart 全部损坏。Pivot 到纯 YAML Kustomize 是明智选择:
- ArgoCD 原生消费 Kustomize (#19 下一步无缝对接, 不需 Helm chart provider)
- kubectl 1.14+ 内置支持, 零额外工具依赖
- overlay 机制多环境复用 base, 表达能力不上 Helm chart
- secretGenerator/configMapGenerator 代替 Helm secret/configmap template

### 设计要点
- **base/ 产品资源 12 份**: namespace + postgres StatefulSet/Service + backend/rag/web Deployment+Service + backend ConfigMap + secretGenerator 5 key + configMapGenerator rag env + image 钉捆 2.0.0。
- **overlays/dev**: 1 副本 + NodePort 30080/30880 + dev image tag, namespace zhiqian-dev, name prefix `dev-`。
- **overlays/prod**: 3 backend / 2 rag / 2 web + Ingress(nginx+TLS) + patch-resources + secret-patch 示例。
- **Helm 目录**: 7 broken 文件覆写为 deprecation stub, 保留 Chart.yaml/values.yaml 为架构参考。

### 变更项
新增 16 个 Kustomize 文件 + 1 README。覆写 7 个 Helm stub + 1 Helm README。

### 验证
```bash
kubectl kustomize zhiqian/deploy/kustomize/base | head -60
kubectl apply -k zhiqian/deploy/kustomize/overlays/dev
kubectl -n zhiqian-dev get all
```

### 回滚
`git revert c5f375d5 9833e4dc` → Kustomize 目录清除; Helm 目录仍为 stub。

---

## 🟢 Phase 2 milestone (6/6) — 2026-05-21 ✅

LangGraph CRAG + GraphRAG + Temporal + Outlines + Cytoscape + JaCoCo 全部交付。

---

## [v2-step-17] 2026-05-21 — Spring Boot Test ≥0.8

**提交 SHA**: `8cf5f96c` + `2e8cedbb`

Testcontainers + WebMvcTest + JaCoCo 门禁 ≥0.70。

---

## [v2-step-16] 2026-05-21 — Cytoscape.js CKG 可视化

**提交 SHA**: `c3374bf7` + `b31d20e6`

---

## [v2-step-15] 2026-05-21 — Outlines 受约束解码

**提交 SHA**: `8fcb13e3`

---

## [v2-step-14] 2026-05-21 — Temporal durable workflow

**提交 SHA**: `4692d68f` + `39ac14c6`

---

## [v2-step-13] 2026-05-21 — GraphRAG 索引 CKG

**提交 SHA**: `e43729a6`

---

## [v2-step-12] 2026-05-21 — LangGraph-style CRAG

**提交 SHA**: `c881dc77` + `2e76a1a6`

---

## 🟢 Phase 1 milestone (11/11) — 2026-05-21 ✅

DeepSeek + 6 Agent + BGE-M3+RRF + Late Chunking + Langfuse + sqlglot + Monaco + RAGAS。

---

## [v2-step-01..11] 2026-05-21 — 详 git log

`913006c0` `790b10f2` `8d4fff1d` `d6b4ac58` `104381a8` `4670edd5` `ceb27034` `1ca293a2` `7bc3236e`/`4678b735`/`bde6b9a1` `6b3d3dec`/`ce3cbb0f` `4f17463c`
