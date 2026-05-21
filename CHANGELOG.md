# CHANGELOG

> 说明: 以下为智迁云枢 v2 升级正式启动以来的完整提交记录。每步提交同步更新 `UPGRADE_PLAN.md` 状态表。

---

## 🟡 Phase 3 进度 (1/7) — 2026-05-21

**云原生 Kustomize 部署落地**。剩 #19 ArgoCD 脚本 / #20 KubeRay+vLLM / #21 Debezium CDC / #22 pgloader/MTK / #23 MCP Server / #24 A2A 协议 共 6 提交。

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
- **base/ 产品资源 12 份逆序列化**:
  - namespace.yaml (zhiqian ns)
  - postgres-statefulset.yaml + postgres-service.yaml (PostgreSQL 16-alpine + 10Gi PVC + pg_isready probe)
  - backend-deployment.yaml + backend-service.yaml + backend-configmap.yaml (Spring Boot 3.2.5 + actuator probe + JaCoCo 在 #17 启, 资源 200m−1500m / 512Mi−2Gi)
  - rag-deployment.yaml + rag-service.yaml (FastAPI + envFrom configMap + DEEPSEEK_API_KEY secret, 资源 200m−2000m / 512Mi−4Gi)
  - web-deployment.yaml + web-service.yaml (Vue 3 nginx static, 资源 50m−200m)
  - kustomization.yaml (资源联合 + secretGenerator 5 key 占位值 + configMapGenerator rag env + image 钉捆 2.0.0)
- **overlays/dev**: 1 副本, 低内存 rag 2Gi, web Service 改 NodePort 30080, backend NodePort 30880, image tag=dev, namespace zhiqian-dev, name prefix `dev-`。单机/本地 minikube/kind 一键起。
- **overlays/prod**: 3 backend / 2 rag / 2 web 副本, ingress.yaml (nginx + TLS) + patch-resources.yaml (提资源 backend 500m−3000m / 1Gi−4Gi, rag 500m−4000m / 1Gi−6Gi) + secret-patch.yaml (示例格式, 生产走 External Secrets/Sealed Secrets/Vault)。
- **Helm 目录 deprecation**: 覆写 7 个 broken 文件 (`_helpers.tpl`, `backend-*.yaml`, `serviceaccount.yaml`) 为 stub 指向 Kustomize, 保留 `Chart.yaml`/`values.yaml` 为架构参考文档。补 `deploy/helm/README.md` 解释 pivot 原委。

### 变更项
新增 16 个 Kustomize 文件:
- `deploy/kustomize/base/{kustomization.yaml,namespace.yaml,postgres-statefulset.yaml,postgres-service.yaml,backend-{configmap,deployment,service}.yaml,rag-{deployment,service}.yaml,web-{deployment,service}.yaml}`
- `deploy/kustomize/overlays/dev/kustomization.yaml`
- `deploy/kustomize/overlays/prod/{kustomization.yaml,ingress.yaml,patch-resources.yaml,secret-patch.yaml}`
- `deploy/kustomize/README.md`

覆写 7 个 Helm 文件为 deprecation stub + 新增 `deploy/helm/README.md`。

### 验证
```bash
# 1) 检查渲染产出
kubectl kustomize zhiqian/deploy/kustomize/base | head -60
kubectl kustomize zhiqian/deploy/kustomize/overlays/dev | grep -E '^(kind|name):' | head -30
kubectl kustomize zhiqian/deploy/kustomize/overlays/prod | grep -E '^(kind|name):'

# 2) dev 一键部署 (minikube/kind)
kubectl apply -k zhiqian/deploy/kustomize/overlays/dev
kubectl -n zhiqian-dev get all
kubectl -n zhiqian-dev port-forward svc/dev-zhiqian-web 8080:80  # -> http://localhost:8080

# 3) prod (记得先 patch 真 secret)
kubectl apply -k zhiqian/deploy/kustomize/overlays/prod
kubectl -n zhiqian get ing zhiqian  # 看 Ingress
```

### 回滚
`git revert c5f375d5 9833e4dc` → Kustomize 目录清除; Helm 目录仍为 deprecated stub。不影响 backend/rag/web/docker compose 主部署路径。

---

## 🟢 Phase 2 milestone (6/6) — 2026-05-21 ✅

**Agent + GraphRAG + Workflow + 约束解码 + 可视化 + 测试覆盖率 全部交付**。

---

## [v2-step-17] 2026-05-21 — Spring Boot Test ≥0.8

**提交 SHA**: `8cf5f96c` + `2e8cedbb`

Testcontainers + WebMvcTest + JaCoCo 门禁 ≥0.70 渐进 + `@SpringBootTest` context loads + 11 测试文件。

---

## [v2-step-16] 2026-05-21 — Cytoscape.js CKG 可视化

**提交 SHA**: `c3374bf7` + `b31d20e6`

fcose layout + /api/ckg/graph demo 图 + /ckg 路由。

---

## [v2-step-15] 2026-05-21 — Outlines 受约束解码

**提交 SHA**: `8fcb13e3`

DeepSeek JSON mode 默认 + Outlines 双后端 + pydantic v2 retry 三轮。

---

## [v2-step-14] 2026-05-21 — Temporal durable workflow

**提交 SHA**: `4692d68f` + `39ac14c6`

6 stage activity + QueryMethod + docker profile=temporal。

---

## [v2-step-13] 2026-05-21 — GraphRAG 索引 CKG

**提交 SHA**: `e43729a6`

Louvain-Lite + local/global 双查询。

---

## [v2-step-12] 2026-05-21 — LangGraph-style CRAG

**提交 SHA**: `c881dc77` + `2e76a1a6`

Mini StateGraph + 3 路评估 + DuckDuckGo 补救。

---

## 🟢 Phase 1 milestone (11/11) — 2026-05-21 ✅

DeepSeek + 6 Agent + BGE-M3+RRF + Late Chunking + Langfuse 双端 + sqlglot + Monaco Diff + RAGAS。

---

## [v2-step-11] 2026-05-21 — RAGAS + 20 条 golden set

**提交 SHA**: `4f17463c`

---

## [v2-step-10] 2026-05-21 — Monaco SQL Diff

**提交 SHA**: `6b3d3dec` + `ce3cbb0f`

---

## [v2-step-09] 2026-05-21 — sqlglot AST 转译

**提交 SHA**: `7bc3236e` + `4678b735` + `bde6b9a1`

---

## [v2-step-08] 2026-05-21 — Langfuse Java SDK

**提交 SHA**: `1ca293a2`

---

## [v2-step-07] 2026-05-21 — Langfuse rag 端

**提交 SHA**: `ceb27034`

---

## [v2-step-06] 2026-05-21 — Late + 语义分块

**提交 SHA**: `4670edd5`

---

## [v2-step-05] 2026-05-21 — Qdrant + 3 路 RRF

**提交 SHA**: `104381a8`

---

## [v2-step-04] 2026-05-21 — BGE-M3 + bge-reranker-v2-m3

**提交 SHA**: `d6b4ac58`

---

## [v2-step-03] 2026-05-21 — LLM 驱动 6 Agent

**提交 SHA**: `8d4fff1d`

---

## [v2-step-02] 2026-05-21 — DeepSeek LLM 客户端

**提交 SHA**: `790b10f2`

---

## [v2-step-01] 2026-05-21 — v2 路线图基线

**提交 SHA**: `913006c0`
