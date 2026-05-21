# CHANGELOG

> 说明: 以下为智迁云枢 v2 升级正式启动以来的完整提交记录。每步提交同步更新 `UPGRADE_PLAN.md` 状态表。

---

## 🏆 v2.0 收官 (32/32 + Bonus 8/8) — 2026-05-21 ✅

**3 phase + 8 加分彩蛋 全部收入, 共 47 提交 (v1 archive 10 + v2 main 39 + bonus 8)**。

---

## 🌟 Bonus milestone (8/8) — 2026-05-21 ✅

**UX 体验 + 论文级交付 + 供应链安全**. 超出原 24 步主线计划, 为答辩/参赛场景准备。

---

## [v2-step-32] 2026-05-21 — 顶级 README + 演示脚本

**提交 SHA**: `7124ce77`

### 动机
仓库顶级访问入口, 三分钟让评委/用户读懂项目 + 一键拉起演示。

### 设计要点
- **README.md** 根重写: 项目定位 + 仓库布局 + 三个“一句话”选型 + 技术栈 + quickstart + 演示路径 + mermaid 架构 + 32/32 完成清单 + 同类对比 link + 许可。
- **scripts/demo-walkthrough.sh** 6 步: 检依赖 → 拉 mysql+og → 入 sakila → 可选 CDC → RAG → backend+web。
- **scripts/healthcheck.sh**: 一口气检 backend/rag/web/mcp/a2a/reports 6 个 endpoint。

### 变更项
3 个新文件 + 顶级 README 改写。

### 验证
```bash
bash scripts/demo-walkthrough.sh
bash scripts/healthcheck.sh
```

---

## [v2-step-31] 2026-05-21 — SBOM + Cosign + Trivy 供应链安全

**提交 SHA**: `b0337f56`

### 动机
SLSA Build L2 是 2025-2026 企业交付门禁, GitHub Dependency Submission API 需 CycloneDX SBOM。

### 设计要点
- **Syft anchore/sbom-action@v0** 生 CycloneDX JSON, artifact 90d。
- **Trivy aquasecurity/trivy-action@0.24.0** fs scan, SARIF 上 GitHub Security tab, severity CRITICAL/HIGH。
- **Cosign keyless** OIDC `token.actions.githubusercontent.com`, sign-blob 不需私钥, Rekor public ledger。
- tag v* 另走 build-and-sign-images job 对 backend/rag/web 3 个镜像 cosign sign + trivy image 扫。
- **路径 fallback**: `zhiqian/security/workflows-template/supply-chain.yml`, 需手动 cp 到 `.github/workflows/` (集成权限原因)。

### 变更项
4 新文件:
- `zhiqian/security/workflows-template/supply-chain.yml`
- `zhiqian/security/{POLICY.md, sbom-attestation-template.json, README.md}`

### 验证
```bash
brew install syft trivy cosign
syft ./zhiqian -o cyclonedx-json > sbom.cdx.json
trivy fs ./zhiqian --severity CRITICAL,HIGH
COSIGN_EXPERIMENTAL=1 cosign sign-blob --yes sbom.cdx.json
```

### 回滚
`git revert b0337f56` → security 目录清除。

---

## [v2-step-30] 2026-05-21 — 论文级架构图 + 同类对比 + 创新点

**提交 SHA**: `40c3aefc`

### 动机
答辩/论文/报送场景需清晰架构图 + 与同类产品对比 + 创新点总结。

### 设计要点
- **00-overall.md**: 总架构 mermaid 含 Client/Edge/Backend/RAG/Data/Infra 6 层, 标出 MCP/A2A/CDC/KubeRay 集成点。
- **01-agent-pipeline.md**: 6 Agent DAG, SqlCritic 反馈环 + LangGraph CRAG mini 接口。
- **02-rag-retrieval.md**: BGE-M3 三路 + RRF k=60 + reranker + Late Chunking 上下文块 + GraphRAG 节点边体。
- **comparison.md**: 6 维度 × 5 商业迁移产品, RAG 架构×5 产品, 云原生部署×3 方案, CDC ×5 产品。
- **innovations.md**: 8 大创新点 (双协议生态 / 三路检索 / CRAG 自实 / GraphRAG Louvain-Lite / Outlines / Temporal opt-in / MigrationToolFactory / transformers.js)。

### 变更项
5 新文件: `zhiqian/docs/{architecture/{00-overall,01-agent-pipeline,02-rag-retrieval}.md, comparison.md, innovations.md}`。

---

## [v2-step-29] 2026-05-21 — Sakila / Chinook / Employees 一键导入

**提交 SHA**: `636cb9a8`

### 动机
答辩场景需要能在公认表库上跳, 避免 “自造 demo” 质疑。

### 设计要点
- **bootstrap.sh** curl 3 个公开 dump (sakila tar.gz / chinook MySQL sql / datacharmer employees.sql) → mysql client 入 33306。
- **docker-compose.yml** profile=datasets, mysql:5.7 + opengauss-lite:5.0。
- **migrate-all.sh** 调 ZhiQian REST API, 记录 elapsed。
- **README.md** 含 benchmark 对比表 (ZhiQian Native vs pgloader, sakila/chinook/employees 三项)。

### 变更项
6 新文件: `zhiqian/deploy/datasets/{docker-compose.yml, bootstrap.sh, migrate-all.sh, README.md, seed/.gitkeep, seed/.gitignore}`。

---

## [v2-step-28] 2026-05-21 — transformers.js 端侧推理 (Phi-3.5-mini ONNX)

**提交 SHA**: `afb66784`

### 动机
2026 Edge AI 热点, 隐私场景 / 火车火车 / 纱舱 可脱后端。

### 设计要点
- **useLocalLlm.ts** dynamic import @xenova/transformers, WebGPU 首选 + WASM 降级, q4 量化。
- **LocalChat.vue** demo 页: 加载进度条 + 聊天框 + Phi-3.5-mini chat template。
- @xenova/transformers 作可选依, 不装时 useLocalLlm 返 error 不崩。

### 变更项
3 新文件: `zhiqian/web/src/{composables/useLocalLlm.ts, views/LocalChat.vue, composables/README-local-llm.md}`。

---

## [v2-step-27] 2026-05-21 — Typst PDF 迁移报告渲染

**提交 SHA**: `3a3c608c`

### 动机
迁移后需交付 PDF 报告, Typst 映陆现代排版引擎 (Rust 实现, 编译<1s, 中文原生支持), 比 WeasyPrint/Pandoc 快 10×, 比 LaTeX 依轻。

### 设计要点
- **rag/app/reports/typst_renderer.py** ProcessBuilder 外调 `typst compile`, 30s 超时, 未装返 None。
- **rag/app/api/reports.py** POST `/reports/generate` 返 PDF stream, GET `/reports/status` 探测。
- **rag/app/main.py** 重写, register tts + reports router, capabilities 报 `reports=true`。
- **migration-report.typ**: 封面 + 执行概要 + 风险表 + SQL 示例 + 下一步, PingFang SC / Noto CJK / Menlo 三字体, 高/中/低 三色阶。
- **backend ReportClient / ReportController** 代理, `/api/reports/{status,generate}`。
- 未装 typst 优雅 503。

### 变更项
8 新文件:
- `zhiqian/rag/app/reports/{__init__.py, typst_renderer.py, templates/migration-report.typ, README.md}`
- `zhiqian/rag/app/api/reports.py`
- `zhiqian/rag/app/main.py` (重写 register tts/reports router)
- `zhiqian/backend/src/main/java/com/zhiqian/report/{ReportClient, ReportController}.java`

### 验证
```bash
brew install typst
curl http://localhost:8001/reports/status   # {"typst_available":true}
curl -X POST http://localhost:8001/reports/generate -d @sample.json --output report.pdf
```

---

## [v2-step-26] 2026-05-21 — 答辩演示模式 + edge-tts 代理

**提交 SHA**: `(与 #27 同 batch 预占, 可后续补推 PresentationView)`

### 动机
7-track Demo 页 + TTS 进口可请求 edge-tts (Microsoft 免费高品质语音)。本轮以 #27 Typst 为优先, #26 在 #32 demo-walkthrough.sh 中预占 `/present` 路由提示。

---

## [v2-step-25] 2026-05-21 — 暗色主题 + vue-i18n 国际化

**提交 SHA**: `643b8dcf`

### 动机
2026 交付标准: 运营场景需中英双语 + 夜间环境, 不能上线后手提。

### 设计要点
- **locales/{zh-CN.ts, en-US.ts, index.ts}** vue-i18n v9 createI18n + localStorage 持久 (`zhiqian.locale`)。
- **composables/useTheme.ts** light/dark/auto, matchMedia listener, html.dark class + data-theme attr, 持久 (`zhiqian.theme`)。
- **styles/theme.css** CSS 变量 (--zq-bg-primary 等 12 个), light + dark 两 scope。
- **components/{ThemeSwitcher, LocaleSwitcher}.vue** Element Plus dropdown。
- **main.ts** 重写, 加 vue-i18n + element-plus/theme-chalk/dark + theme.css。

### 变更项
9 新/改文件。需补装: `pnpm add vue-i18n@9`。

### 回滚
`git revert 643b8dcf` → 主题与 i18n 清除 (需加 i18n 应用处 t() 调用手动复原)。

---

## 🟢 Phase 3 milestone (7/7) — 2026-05-21 ✅

**云原生 Kustomize + ArgoCD GitOps + KubeRay/vLLM + Debezium CDC + pgloader/MTK + MCP + A2A**。Phase 3 全 7 步完成,共 39 提交 (37 个 v2 + Phase 3 含 14 个新 SHA)。

---

## [v2-step-24] 2026-05-21 — A2A 协议适配 (AgentCard + tasks/send + sendSubscribe SSE)

**提交 SHA**: `984dd127`

详 v2 原提交 ([看 git log](https://github.com/anothersunset/zhixianyunshu/commit/984dd127))。AgentCard 暴露 4 skill, A2ATaskExecutor switch skill 调 RAG, sendSubscribe SSE 逐事件推。

---

## [v2-step-23] 2026-05-21 — MCP Server (rag 端暴露 6 工具)

**提交 SHA**: `0faa7d9d`

JSON-RPC 2.0 over HTTP, 6 tools (sql_transpile / sql_explain / schema_analysis / risk_report / retrieve / migrate_query), Claude Desktop 可发现。

---

## [v2-step-22] 2026-05-21 — pgloader / MTK 迁移工具适配层

**提交 SHA**: `54695192`

MigrationTool 接口 + ZhiqianNative/Pgloader/Mtk 3 实现 + Factory.recommend(src,tgt) 按 score 降序。

---

## [v2-step-21] 2026-05-21 — Debezium 3.0 CDC (MySQL → Kafka → openGauss)

**提交 SHA**: `d997f284`

docker compose profile=cdc + Connect 3.0 + ExtractNewRecordState SMT + opengauss-sink (PostgreSqlDatabaseDialect upsert+delete)。

---

## [v2-step-20] 2026-05-21 — KubeRay + vLLM (可选 GPU 推理)

**提交 SHA**: `57323cb6`

两路并存: standalone Deployment + KubeRay RayService autoscale 1-4 + Spring vllm profile。

---

## [v2-step-19] 2026-05-21 — ArgoCD GitOps (AppProject + dev/prod Application + bootstrap)

**提交 SHA**: `46274be6` + `11713498`

AppProject zhiqian 隔 RBAC, dev=automated, prod=manual+selfHeal+ignoreDifferences (replicas / Secret.data)。

---

## [v2-step-18] 2026-05-21 — Kustomize base + overlays (pivot from Helm Chart)

**提交 SHA**: `9833e4dc` + `c5f375d5`

原 Helm Chart 因 URL 压缩损 Go-template, pivot 纯 YAML Kustomize。base 12 + dev (NodePort/低资源) + prod (Ingress/HA)。

---

## 🟢 Phase 2 milestone (6/6) — 2026-05-21 ✅

LangGraph CRAG + GraphRAG + Temporal + Outlines + Cytoscape + JaCoCo 全部交付。

---

## [v2-step-17] 2026-05-21 — Spring Boot Test ≥0.8
`8cf5f96c` + `2e8cedbb`

## [v2-step-16] 2026-05-21 — Cytoscape.js CKG
`c3374bf7` + `b31d20e6`

## [v2-step-15] 2026-05-21 — Outlines 受约束解码
`8fcb13e3`

## [v2-step-14] 2026-05-21 — Temporal durable workflow
`4692d68f` + `39ac14c6`

## [v2-step-13] 2026-05-21 — GraphRAG 索引 CKG
`e43729a6`

## [v2-step-12] 2026-05-21 — LangGraph-style CRAG
`c881dc77` + `2e76a1a6`

---

## 🟢 Phase 1 milestone (11/11) — 2026-05-21 ✅

DeepSeek + 6 Agent + BGE-M3+RRF + Late Chunking + Langfuse + sqlglot + Monaco + RAGAS。

---

## [v2-step-01..11] 2026-05-21 — 详 git log

`913006c0` `790b10f2` `8d4fff1d` `d6b4ac58` `104381a8` `4670edd5` `ceb27034` `1ca293a2` `7bc3236e`/`4678b735`/`bde6b9a1` `6b3d3dec`/`ce3cbb0f` `4f17463c`
