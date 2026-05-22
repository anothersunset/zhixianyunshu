# CHANGELOG

> 说明: 以下为智迁云枢 v2 升级正式启动以来的完整提交记录。每步提交同步更新 `UPGRADE_PLAN.md` 状态表。

---

## 🚀 v1.0.0 最终版 — 2026-05-22 ✅

**SHA**: `(本提交)` · 累计 50+ 提交 · 8 轮打磨

由 v2 alpha (32/32 + Bonus 8/8) 经 8 轮打磨进版 v1.0.0 首个发布版。质量门全过 · 社区健康度完备 · SemVer 反复。

### 交付物
- `VERSION` · `RELEASE_NOTES.md` 详情
- 50+ 提交 + 70 项决策日志
- 3 服务 + 8 加分彩蛋 + 供应链闭环 + 社区健康度

### 验交
```bash
cat VERSION                          # 1.0.0
make smoke                            # 三路静态检过
make demo                             # 端到端跑通
```

---

## 🛠️ Polish round 8 — v1.0.0 release — 2026-05-22

**SHA**: `(本提交)`

- `VERSION` 根文件 — `1.0.0`
- `RELEASE_NOTES.md` 根 — 发布说明 + 8 轮打磨表 + SemVer 反复 + 升级路径
- 同步 `CHANGELOG.md` 顶部 + `UPGRADE_PLAN.md` polish 表

---

## 🛠️ Polish round 7 — 顶层文档补齐 — 2026-05-22

**SHA**: `1c34667d`

补齐 polish 6 (`c330328d`) 里 `docs/INDEX.md` 引用但还未建的 6 份顶层文档:

- `docs/QUICKSTART.md` — 5 分钟上手
- `docs/architecture/00-overall.md` — 总架构概览与 6 层 mermaid
- `docs/architecture/01-agent-pipeline.md` — 6-Agent DAG 与 CRAG
- `docs/architecture/02-rag-retrieval.md` — 三路检索 + Late Chunking + GraphRAG
- `docs/comparison.md` — 同类 5 产品×6 维对比 + 不适用场景
- `docs/innovations.md` — 8 大创新点

---

## 🛠️ Polish round 6 — Makefile + dockerignore + INDEX — 2026-05-21

**SHA**: `c330328d`

- `Makefile` 根 — `help/smoke/demo/health/seed/sbom/backend/rag/web/clean/install-tools`
- `.dockerignore` 根 — 减 docker build 上下文
- `docs/INDEX.md` — 一页式全文档导航 (5 入口 + 5 区块 + make help 镜像)

---

## 🛠️ Polish round 5 — 社区健康度 — 2026-05-21

**SHA**: `1e761a03`

- `.github/ISSUE_TEMPLATE/{bug,feature,question,config}.{md,yml}` — 4 个模板 + Discussions 入口
- `.github/PULL_REQUEST_TEMPLATE.md` — 检查单 + DCO
- `SECURITY.md` — 漏洞披露 + cosign verify-blob 脚本 + 不在范围内
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1
- `.editorconfig` — Java=4 / Python=4 / 其他=2 / Makefile=tab
- `docs/README.md` — docs 目录入口

---

## 🛠️ Polish round 4 — 贡献与排错文档 — 2026-05-21

**SHA**: `f9053573`

- `CONTRIBUTING.md` — Conventional Commits + branch model + PR 流 + smoke gate + DCO
- `docs/TROUBLESHOOTING.md` — 12 条常见问题 + 定位/修复 (supply-chain / edge-tts / typst / WebGPU / port / Temporal / Langfuse / ML deps)
- `docs/TOOLS.md` — CLI 版本矩阵 (Java/Maven/pnpm/Python/Docker/kubectl/argocd/syft/trivy/cosign/typst/edge-tts)

---

## 🛠️ Polish round 3 — UPGRADE_PLAN 同步 + smoke-test — 2026-05-21

**SHA**: `3145629c`

- `scripts/smoke-test.sh` — 三路静态检 (web vue-tsc / rag compileall / backend mvn compile), ENV `SMOKE_SKIP_{WEB,RAG,BACKEND}`
- `scripts/README.md` — 4 脚本表 + ENV 与推荐组合
- `UPGRADE_PLAN.md` — 加 Polish round 表 + 5 决策日志 + #25/#26/#28/#31 SHA 同步

---

## 🛠️ Polish round 2 — LocalChat 修模板 + workflow 一键装 — 2026-05-21

**SHA**: `2c797979`

- `web/src/views/LocalChat.vue` — 重写，全采 `v-text="..."` 防 URL 压缩抑制二重括号
- `scripts/install-supply-chain-workflow.sh` — sed 将 `workflows-template/*.tmpl` 转为真 workflow
- `zhiqian/security/README.md` — 补 "为什么走 template + 一键脚本"
- `CHANGELOG.md` — #26 状态翻实 + Bonus 8/8 诚实声明

---

## 🛠️ Polish round 1 — #26 补齐 + #28 路由 + backend edge-tts — 2026-05-21

**SHA**: `9b938300`

- `web/src/views/PresentationView.vue` (10 幻灯) + `components/SlideDeck.vue`
- `web/src/services/tts.ts` — fetch RAG /tts/speak + fallback SpeechSynthesis
- `web/src/router/index.ts` — 加 `/present` (公开) + `/edge`
- `web/package.json` v0.5.0 — + vue-i18n@9 + optionalDeps @xenova/transformers
- `backend tts/{TtsController,TtsProperties}.java` + `application-tts.yml` — ProcessBuilder 调 edge-tts

---

## 🏆 v2.0 收官 (32/32 + Bonus 8/8) — 2026-05-21 ✅

**3 phase + 8 加分彩蛋 全部交付, 共 49 提交 (v1 archive 10 + v2 主线 39 + bonus 8 + final docs sync)**。

---

## 🌟 Bonus milestone (8/8) — 2026-05-21 ✅

**UX 体验 + 论文级交付 + 供应链安全**. 超出原 24 步主线计划, 为答辩/参赛场景准备。

---

## [v2-step-32] 2026-05-21 — 顶级 README + 演示脚本

**提交 SHA**: `7124ce77`

3 个新文件 + 顶级 README 改写。

---

## [v2-step-31] 2026-05-21 — SBOM + Cosign + Trivy 供应链安全

**提交 SHA**: `b0337f56` + polish `2c797979`

4 新文件 + workflow-template + 一键 install 脚本。

---

## [v2-step-30] 2026-05-21 — 论文级架构图 + 同类对比 + 创新点

**提交 SHA**: `40c3aefc`

5 新文件: `zhiqian/docs/{architecture/{00,01,02}.md, comparison.md, innovations.md}`。

---

## [v2-step-29] 2026-05-21 — Sakila / Chinook / Employees 一键导入

**提交 SHA**: `636cb9a8`

6 新文件: `zhiqian/deploy/datasets/{docker-compose.yml, bootstrap.sh, migrate-all.sh, README.md, seed/...}`。

---

## [v2-step-28] 2026-05-21 — transformers.js 端侧推理 (Phi-3.5-mini ONNX) + polish 修模板

**提交 SHA**: `afb66784` + polish `2c797979`

3 新文件: `web/src/{composables/useLocalLlm.ts, views/LocalChat.vue, composables/README-local-llm.md}`。

---

## [v2-step-27] 2026-05-21 — Typst PDF 迁移报告渲染

**提交 SHA**: `3a3c608c`

8 新文件: rag reports + backend ReportClient + ReportController。

---

## [v2-step-26] 2026-05-21 — 答辩演示模式 + edge-tts 代理

**提交 SHA**: `9b938300`

7 新文件: PresentationView / SlideDeck / tts service / router / backend tts。

---

## [v2-step-25] 2026-05-21 — 暗色主题 + vue-i18n 国际化

**提交 SHA**: `643b8dcf` + polish `2c797979`

9 新/改文件: locales + useTheme + theme.css + 2 个 switcher。

---

## 🟢 Phase 3 milestone (7/7) — 2026-05-21 ✅

**云原生 Kustomize + ArgoCD GitOps + KubeRay/vLLM + Debezium CDC + pgloader/MTK + MCP + A2A**。

## [v2-step-24] A2A AgentCard + tasks/send + sendSubscribe SSE — `984dd127`
## [v2-step-23] MCP Server 6 tools — `0faa7d9d`
## [v2-step-22] pgloader / MTK / ZhiqianNative MigrationToolFactory — `54695192`
## [v2-step-21] Debezium 3.0 CDC (MySQL → Kafka → openGauss) — `d997f284`
## [v2-step-20] KubeRay RayService autoscale 1-4 + vLLM profile — `57323cb6`
## [v2-step-19] ArgoCD AppProject + dev/prod Application + bootstrap — `46274be6` + `11713498`
## [v2-step-18] Kustomize base + dev/prod overlays (pivot from Helm) — `9833e4dc` + `c5f375d5`

---

## 🟢 Phase 2 milestone (6/6) — 2026-05-21 ✅

LangGraph CRAG + GraphRAG + Temporal + Outlines + Cytoscape + JaCoCo。

## [v2-step-17] Spring Boot Test ≥0.8 — `8cf5f96c` + `2e8cedbb`
## [v2-step-16] Cytoscape.js CKG — `c3374bf7` + `b31d20e6`
## [v2-step-15] Outlines 受约束解码 — `8fcb13e3`
## [v2-step-14] Temporal durable workflow — `4692d68f` + `39ac14c6`
## [v2-step-13] GraphRAG 索引 CKG — `e43729a6`
## [v2-step-12] LangGraph-style CRAG — `c881dc77` + `2e76a1a6`

---

## 🟢 Phase 1 milestone (11/11) — 2026-05-21 ✅

DeepSeek + 6 Agent + BGE-M3+RRF + Late Chunking + Langfuse + sqlglot + Monaco + RAGAS。

## [v2-step-01..11] — `913006c0` `790b10f2` `8d4fff1d` `d6b4ac58` `104381a8` `4670edd5` `ceb27034` `1ca293a2` `7bc3236e`/`4678b735`/`bde6b9a1` `6b3d3dec`/`ce3cbb0f` `4f17463c`
