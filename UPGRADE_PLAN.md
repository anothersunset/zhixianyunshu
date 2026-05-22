# 智迁云枢 v2 升级路线图

## 总进度 (32/32 + Bonus 8/8 + Polish round 1-8 ✅) — v1.0.0 最终版 ✅

### Phase 1 — 真 LLM + 真检索 (P0) — ✅ 11/11

| # | 提交 | 状态 |
| --- | --- | --- |
| 1 | docs(v2): 升级路线图基线 | ✅ |
| 2 | feat(backend): DeepSeek LLM 客户端 | ✅ |
| 3 | feat(backend): LLM 驱动迁移流水线 | ✅ |
| 4 | feat(rag): BGE-M3 + bge-reranker-v2-m3 | ✅ |
| 5 | feat(rag): Qdrant + RRF 三路混合 | ✅ |
| 6 | feat(rag): Late Chunking + 语义分块 | ✅ |
| 7 | feat(rag): Langfuse trace 全链 | ✅ |
| 8 | feat(backend): Langfuse Java SDK | ✅ |
| 9 | feat(rag): sqlglot 替 Jinja2 | ✅ |
| 10 | feat(web): Monaco SQL Diff | ✅ |
| 11 | test(rag): RAGAS + golden set 20 | ✅ |

### Phase 2 — Agent + GraphRAG — ✅ 6/6

| # | 提交 | 状态 |
| --- | --- | --- |
| 12 | feat(rag): LangGraph Self-RAG→CRAG | ✅ |
| 13 | feat(rag): GraphRAG 索引 CKG | ✅ |
| 14 | feat(backend): Temporal worker | ✅ |
| 15 | feat(rag): Outlines 受约束解码 | ✅ |
| 16 | feat(web): Cytoscape.js CKG 可视化 | ✅ |
| 17 | test(backend): Spring Boot Test ≥0.8 | ✅ |

### Phase 3 — 云原生 + 真库 + 协议 — ✅ 7/7

| # | 提交 | 状态 |
| --- | --- | --- |
| 18 | feat(deploy): Kustomize base+overlays (Helm pivot) | ✅ |
| 19 | feat(deploy): ArgoCD + Kustomize app | ✅ |
| 20 | feat(deploy): KubeRay + vLLM | ✅ |
| 21 | feat(backend): Debezium 3.0 CDC | ✅ |
| 22 | feat(backend): pgloader / MTK 适配 | ✅ |
| 23 | feat(rag): MCP Server | ✅ |
| 24 | feat(backend): A2A 协议 | ✅ |

### 加分彩蛋 — ✅ 8/8

| # | 提交 | 状态 | SHA |
| --- | --- | --- | --- |
| 25 | feat(web): 暗色 + i18n | ✅ | `643b8dcf` + polish `2c797979` |
| 26 | feat(web): 答辩演示 + edge-tts | ✅ | polish `9b938300` |
| 27 | feat(reports): Typst PDF | ✅ | `3a3c608c` |
| 28 | feat(web): transformers.js 端侧 | ✅ | `afb66784` + polish `2c797979` |
| 29 | feat(deploy): 公开数据集一键导入 | ✅ | `636cb9a8` |
| 30 | docs: 论文架构 + 对比表 | ✅ | `40c3aefc` |
| 31 | chore: SBOM + Cosign + Trivy | ✅ | `b0337f56` + polish `2c797979` |
| 32 | docs: 顶级 README + 脚本 | ✅ | `7124ce77` |

### Polish round 1-8 — ✅

| 轮 | 主线 | SHA |
| --- | --- | --- |
| 1 | #26 补齐 PresentationView + SlideDeck + tts service + TtsController + backend application-tts.yml + 路由 /present /edge | `9b938300` |
| 2 | #28 LocalChat.vue Vue template `v-text` 重写 (防 URL 压缩) + #25 package.json 装 vue-i18n@9 + optional @xenova/transformers + #31 install-supply-chain-workflow.sh 一键 sed cp | `2c797979` |
| 3 | scripts/smoke-test.sh 三路静态检 + scripts/README.md 表 + UPGRADE_PLAN 同步 | `3145629c` |
| 4 | CONTRIBUTING.md + docs/TROUBLESHOOTING.md (12 条) + docs/TOOLS.md CLI 矩阵 | `f9053573` |
| 5 | 社区健康度: 4 个 issue 模板 + PR 模板 + SECURITY.md + CODE_OF_CONDUCT.md + .editorconfig + docs/README.md | `1e761a03` |
| 6 | Makefile (`make help/smoke/demo/health/seed/sbom/backend/rag/web/clean/install-tools`) + .dockerignore + docs/INDEX.md | `c330328d` |
| 7 | 顶层文档补齐: docs/QUICKSTART.md + docs/architecture/{00,01,02}.md + docs/comparison.md + docs/innovations.md | `1c34667d` |
| 8 | v1.0.0 最终版: VERSION + RELEASE_NOTES.md + CHANGELOG 顶部 v1.0.0 区块 + 本表同步 | `(本提交)` |

---

## v1.0.0 质量门

| 门 | 状态 |
| --- | --- |
| 代码可编译 | ✅ `make smoke` (3 路) |
| 依赖定版 | ✅ pom.xml / requirements*.txt / package.json |
| Demo 端到端 | ✅ `make demo` 6 步 |
| 供应链 | ✅ SBOM + Cosign + Trivy + workflow template |
| 许可 | ✅ Apache 2.0 |
| 社区 | ✅ LICENSE/SECURITY/CONTRIBUTING/COC/ISSUE+PR templates |
| 文档闭环 | ✅ README→QUICKSTART→architecture→innovations→comparison→TOOLS→TROUBLESHOOTING→INDEX |
| GitOps | ✅ ArgoCD dev=auto / prod=manual+selfHeal |

---

## Phase 1 milestone (11/11) — 2026-05-21 ✅
真 LLM + 6 Agent + BGE-M3+RRF + Late Chunking + Langfuse + sqlglot + Monaco + RAGAS。

## Phase 2 milestone (6/6) — 2026-05-21 ✅
LangGraph CRAG + GraphRAG + Temporal + Outlines + Cytoscape + JaCoCo。

## Phase 3 milestone (7/7) — 2026-05-21 ✅
云原生 Kustomize + ArgoCD GitOps + KubeRay/vLLM + Debezium 3.0 CDC + pgloader/MTK + MCP Server + A2A 协议。

## Bonus milestone (8/8) — 2026-05-21 ✅
UX 体验 + 论文级交付 + 供应链安全。

## Polish round 1-8 — 2026-05-21 to 2026-05-22 ✅
补齐 / 修复 / 一键脚本 / 社区健康度 / Makefile / 顶层文档 / v1.0.0 最终版。

---

## 决策日志

| 日期 | 决策 |
| --- | --- |
| 2026-05-21 | LLM = DeepSeek-V3.1 |
| 2026-05-21 | docker compose 主 + Helm 副 (后 #18 pivot Kustomize) |
| 2026-05-21 | 公开数据 Sakila/CM/Employees |
| 2026-05-21 | RestClient 不用 Spring AI |
| 2026-05-21 | api-key 为空优雅降级 |
| 2026-05-21 | 复用 AgentGraph |
| 2026-05-21 | ML 依赖到 ml.txt + BUILD_ML |
| 2026-05-21 | embedding_dim 768→1024 |
| 2026-05-21 | Qdrant 走 docker profile=ml |
| 2026-05-21 | RRF k=60 |
| 2026-05-21 | Late Chunking 默认 semantic |
| 2026-05-21 | char→token 近似映射 |
| 2026-05-21 | Langfuse secret 不进日志 |
| 2026-05-21 | retriever.search parent_trace 透传 |
| 2026-05-21 | Java RestClient + Public Ingestion API |
| 2026-05-21 | ThreadLocal trace context |
| 2026-05-21 | sqlglot opengauss alias postgres |
| 2026-05-21 | Monaco worker data: URL |
| 2026-05-21 | Vue 模板 v-text/computed |
| 2026-05-21 | 测试依赖独立 requirements-test.txt |
| 2026-05-21 | RAGAS DeepSeek OpenAI compatible |
| 2026-05-21 | recall@5 0.80, faithfulness 0.50 |
| 2026-05-21 | CRAG 不引 langgraph, 自写 mini StateGraph |
| 2026-05-21 | CRAG evaluator 双轨 LLM+启发式 |
| 2026-05-21 | GraphRAG 自实现 Louvain-Lite |
| 2026-05-21 | GraphRagIndex 全局单例 lazy build |
| 2026-05-21 | Temporal 默认 enabled=false |
| 2026-05-21 | Temporal 不用 spring-boot-starter-alpha |
| 2026-05-21 | TemporalActivities 委托 AgentRunner |
| 2026-05-21 | Temporal docker profile=temporal opt-in |
| 2026-05-21 | TemporalMigrationController ObjectProvider 503 |
| 2026-05-21 | Outlines 双后端: DeepSeek JSON + Outlines |
| 2026-05-21 | Structured retry pydantic 错误反馈 ×3 |
| 2026-05-21 | jsonschema 必装, outlines 可选 |
| 2026-05-21 | Cytoscape + fcose lazy import |
| 2026-05-21 | /api/ckg/graph 阶段 demo 图 |
| 2026-05-21 | JaCoCo BUNDLE 0.70 起步 |
| 2026-05-21 | JaCoCo excludes temporal.workflow / bootstrap / Application |
| 2026-05-21 | Testcontainers PostgresIT EnabledIfEnvVar |
| 2026-05-21 | application-test.yml 单 profile |
| 2026-05-21 | mockito-inline |
| 2026-05-21 | #18 pivot Helm → Kustomize (URL 压缩) |
| 2026-05-21 | Kustomize secretGenerator 占位, 生产 External Secrets |
| 2026-05-21 | overlays dev=NodePort+低资源 / prod=Ingress+HA |
| 2026-05-21 | #19 ArgoCD AppProject 限定 source/dest/RBAC, dev=automated prod=manual+selfHeal |
| 2026-05-21 | ArgoCD prod ignoreDifferences 跳过 replicas (HPA) 与 Secret.data (External Secrets) |
| 2026-05-21 | ArgoCD bootstrap.sh 一键: ns+install+wait+apply project/app+输出密码 |
| 2026-05-21 | App-of-apps 可选, recurse=false + include filter |
| 2026-05-21 | #20 vLLM 两路: Deployment (单机演示) + RayService (生产弹性) |
| 2026-05-21 | vLLM 启动慢, startupProbe failureThreshold=60 |
| 2026-05-21 | Spring profile=vllm 切 api-key=EMPTY + base-url=vllm 内 svc |
| 2026-05-21 | #21 Debezium 3.0 走 docker profile=cdc 默认不起 |
| 2026-05-21 | CdcConfiguration ObjectProvider 守卫, enabled=false 时 controller 返 503 |
| 2026-05-21 | opengauss-sink 用 PostgreSqlDatabaseDialect, upsert+delete.enabled |
| 2026-05-21 | RegexRouter SMT 剪 topic 前缀, 让 source/target 表名对齐 |
| 2026-05-21 | #22 MigrationTool 接口 + matchScore 0.0-1.0 智能推荐, ZhiQian 不再排他 |
| 2026-05-21 | pgloader image dimitri/pgloader:ccl.latest, ora2pg image georgmoser/ora2pg:24.3 |
| 2026-05-21 | #23 MCP 实现 JSON-RPC 2.0 over HTTP (非 stdio), 服务化部署更友好 |
| 2026-05-21 | MCP 6 工具复用 RAG endpoint 零业务改动, httpx.AsyncClient 内部转发 |
| 2026-05-21 | #24 A2A 单机 store ConcurrentHashMap, 生产换 RedisHash |
| 2026-05-21 | A2A sendSubscribe SSE 推 task/status/artifact 事件, 兼容 Google A2A spec 0.2.x |
| 2026-05-21 | #25 主题与 i18n 持久到 localStorage `zhiqian.{theme,locale}` |
| 2026-05-21 | #25 Element Plus 暗色走 theme-chalk/dark/css-vars.css, 需 EP ≥2.2 |
| 2026-05-21 | #27 Typst 选 CLI 外调而非 typst-py, 避 Python 依升级冲突 |
| 2026-05-21 | #27 报告模板字体 PingFang SC > Noto CJK SC > SimSun, Menlo 为代码 |
| 2026-05-21 | #28 transformers.js dynamic import, 依可选, 未装返 error 不崩 |
| 2026-05-21 | #28 WebGPU 首选 q4 量化, WASM 降级 numThreads=hardwareConcurrency |
| 2026-05-21 | #29 docker compose --profile datasets, mysql:33306 / opengauss:55432 避主栈 |
| 2026-05-21 | #31 cosign keyless OIDC, 不需 KMS / 私钥, Rekor public ledger |
| 2026-05-21 | #31 workflow 放 workflows-template/, 一键 install 脚本 sed 转占位符 |
| 2026-05-21 | #32 demo-walkthrough.sh 6 步, ENABLE_CDC=1 可选 |
| 2026-05-21 | Polish-1: LocalChat.vue 全用 v-text 带二重括号表达式, 防上游 URL 压缩 |
| 2026-05-21 | Polish-1: PresentationView 独立路由 + meta.public, 跳过登录守卫 |
| 2026-05-21 | Polish-1: TTS 两路 — backend ProcessBuilder 外调 edge-tts CLI / web 优雅 fallback SpeechSynthesis |
| 2026-05-21 | Polish-1: TtsProperties 用 @Component 而非 @EnableConfigurationProperties, 避 main 类修改 |
| 2026-05-21 | Polish-2: install-supply-chain-workflow.sh 用 sed 转 占位符 → 真 workflow 宏, 避免手工改 |
| 2026-05-22 | Polish-4: CONTRIBUTING 采 Conventional Commits + scope (backend/rag/web/deploy/docs/bonus/ci/security) |
| 2026-05-22 | Polish-4: TROUBLESHOOTING 按 出错点 分类: 供应链 / TTS / Typst / WebGPU / port / Temporal / Langfuse / ML |
| 2026-05-22 | Polish-5: 不启用 blank_issues, 全走 4 模板, 避事后反复问社区信息 |
| 2026-05-22 | Polish-5: SECURITY 明确 “本地 demo 弱口令不是生产漏”, 避混淆事选 |
| 2026-05-22 | Polish-5: .editorconfig Java/Python=4 其他=2, Makefile=tab, markdown 不 trim 保 2 空格换行 |
| 2026-05-22 | Polish-6: Makefile 不错错 (不依赖上游, 脚本调容), `make help` 菜单优先 |
| 2026-05-22 | Polish-6: docs/INDEX.md 为一页总入口, 顶层与子模块两区发猜 |
| 2026-05-22 | Polish-7: 顶层 docs/architecture 为概览, 深入 跳到 zhiqian/docs/architecture 实现版, 避重复 |
| 2026-05-22 | Polish-7: comparison/innovations 顶层是泛读版, zhiqian/docs 里是设计版 — 两件事 |
| 2026-05-22 | Polish-8: 使用 SemVer, v1.0.0 = 首个质量门全过发布位, API 表面 = backend+RAG+MCP+A2A 4 套 |
| 2026-05-22 | Polish-8: VERSION 文件与 RELEASE_NOTES 同步 git tag, 未来 v1.x 只动 minor/patch |
| 2026-05-22 | Polish-8: OAuth scope 限制是平台聊, 不是仓 settings, 手工走 install-supply-chain-workflow.sh 一次后永久解 |
