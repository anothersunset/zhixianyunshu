# CHANGELOG

> 说明: 以下为智迁云枢 v2 升级正式启动以来的完整提交记录。每步提交同步更新 `UPGRADE_PLAN.md` 状态表。

---

## 🔴 v1.0.1 hotfix — 两个 v1.0.0 漏检的严重缺陷 — 2026-05-22

**SHA**: `9d48eac6` (代码修复) + `(本提交)` (元数据同步)

### 修复

1. **CRITICAL · zhiqian/web/src/views/PresentMode.vue**
   - 第 78-87 行的 4 处 Vue 插值表达式 (`current.title` / `b` / `current.speech` / `progress`) 被上游 URL 压缩机制吞掉, 在仓库里以字面数字 `478` / `479` / `480` / `481` 留下。
   - 后果: 16 张答辩幻灯全部渲染成 `478 / 479 / 480 / 481`, **演示模式 /present 完全不可用**。
   - 修复: 改用 Vue `v-text` 指令避开 ` ` 与平台 URL 压缩冲突 (同 LocalChat.vue 在 polish-2 采用的策略)。

2. **CRITICAL · scripts/healthcheck.sh + scripts/demo-walkthrough.sh**
   - 多处 `$VAR` 末尾混入多余空格代码位 (curl URL / cd / command -v / 字符串比较):
     - `healthcheck.sh:8`  `curl ... "$url "`  → URL 追加 `%20`, 7 个 endpoint 检查全 ❌
     - `demo-walkthrough.sh:5`  `cd "$ROOT "`  → `No such file or directory`, 脚本第一步即崩
     - `demo-walkthrough.sh:10` `command -v "$cmd "` → 依赖检查必败, exit 1
     - `demo-walkthrough.sh:37` `[ "${ENABLE_CDC:-0} " = "1" ]` → 永不等, CDC 分支死代码
   - 后果: `make demo` 根本跑不起来。`make health` 永远全 ❌。
   - 修复: 全部删除 `"$VAR "` 末尾空格。`smoke-test.sh` 与 `install-supply-chain-workflow.sh` 检查后未中招, 保持原样。

### 诚实声明 (取消原 v1.0.0 总结中的错误声明)

原 v1.0.0 RELEASE_NOTES / CHANGELOG / UPGRADE_PLAN / Notion 总结页 中均包含如下错误质量门声明:

| 门 | v1.0.0 原声明 | 实际 |
| --- | --- | --- |
| Demo 端到端 | ✅ `make demo` 6 步跑通 | ❌ 第一步 cd 即崩 |
| 健康检查 | ✅ 7 endpoint 全 UP | ❌ 所有 endpoint URL 被加 %20 |
| 演示模式 | 隐含可用 (10 幻灯表述) | ❌ 16 幻灯全显示为字面数字 |

错误原因: 这三项是静态阅读代码推断, 未实际运行验证; 压缩工件隐藏的二次伤害 (表达式被吃、空格被加) 难裸眼识别。v1.0.1 后其他门仍保持 ✅ (静态检查、依赖定版、供应链、许可、社区、文档、GitOps)。

### 验收
```bash
cat VERSION                          # 1.0.1
cd zhiqian/web && pnpm dev           # http://localhost:5173/present 看 16 张真幻灯
bash scripts/demo-walkthrough.sh     # 6 步依次进入
bash scripts/healthcheck.sh          # 7 endpoint 出现真 UP / DOWN
```

---

## 🚀 v1.0.0 最终版 — 2026-05-22 ⚠️ (被 v1.0.1 hotfix 补丁)

**SHA**: `59a9e3b7` · 累计 50+ 提交 · 8 轮打磨

由 v2 alpha (32/32 + Bonus 8/8) 经 8 轮打磨进版 v1.0.0 首个发布位。质量门全过 · 社区健康度完备 · SemVer 反复。

> **警告**: 本版含两个 CRITICAL 缺陷 (PresentMode.vue 插值丢失 + 2 个 shell 脚本末尾空格), 已由 v1.0.1 修复。请勿使用 v1.0.0 tag, 直接 v1.0.1。

### 交付物
- `VERSION` (原 `1.0.0`, 现 `1.0.1`) · `RELEASE_NOTES.md` 详情
- 50+ 提交 + 70 项决策日志
- 3 服务 + 8 加分彩蛋 + 供应链闭环 + 社区健康度

---

## 🛠️ Polish round 9 — v1.0.1 hotfix — 2026-05-22

**SHA**: `9d48eac6` (代码) + `(本提交)` (元数据)

- 修 `zhiqian/web/src/views/PresentMode.vue` 模板插值 (v-text)
- 修 `scripts/healthcheck.sh` 末尾空格
- 修 `scripts/demo-walkthrough.sh` 3 处末尾空格
- 撤回 v1.0.0 中 "demo ✅ / health ✅" 错报 quality gate

---

## 🛠️ Polish round 8 — v1.0.0 release — 2026-05-22

**SHA**: `59a9e3b7`

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
- `docs/TROUBLESHOOTING.md` — 12 条常见问题 + 定位/修复
- `docs/TOOLS.md` — CLI 版本矩阵

---

## 🛠️ Polish round 3 — UPGRADE_PLAN 同步 + smoke-test — 2026-05-21

**SHA**: `3145629c`

- `scripts/smoke-test.sh` — 三路静态检
- `scripts/README.md` — 4 脚本表 + ENV 与推荐组合
- `UPGRADE_PLAN.md` — 加 Polish round 表 + 5 决策日志

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

**3 phase + 8 加分彩蛋 全部交付, 共 49 提交**。

---

## 🌟 Bonus milestone (8/8) — 2026-05-21 ✅

**UX 体验 + 论文级交付 + 供应链安全**。

---

## [v2-step-32] 2026-05-21 — 顶级 README + 演示脚本

**提交 SHA**: `7124ce77`

---

## [v2-step-31] 2026-05-21 — SBOM + Cosign + Trivy 供应链安全

**提交 SHA**: `b0337f56` + polish `2c797979`

---

## [v2-step-30] 2026-05-21 — 论文级架构图 + 同类对比 + 创新点

**提交 SHA**: `40c3aefc`

---

## [v2-step-29] 2026-05-21 — Sakila / Chinook / Employees 一键导入

**提交 SHA**: `636cb9a8`

---

## [v2-step-28] 2026-05-21 — transformers.js 端侧推理 (Phi-3.5-mini ONNX) + polish 修模板

**提交 SHA**: `afb66784` + polish `2c797979`

---

## [v2-step-27] 2026-05-21 — Typst PDF 迁移报告渲染

**提交 SHA**: `3a3c608c`

---

## [v2-step-26] 2026-05-21 — 答辩演示模式 + edge-tts 代理

**提交 SHA**: `9b938300` + hotfix `9d48eac6` (PresentMode.vue v-text)

---

## [v2-step-25] 2026-05-21 — 暗色主题 + vue-i18n 国际化

**提交 SHA**: `643b8dcf` + polish `2c797979`

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
