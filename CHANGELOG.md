# CHANGELOG

> 说明: 以下为智迁云枢 v2 升级正式启动以来的完整提交记录。每步提交同步更新 `UPGRADE_PLAN.md` 状态表。

---

## 🏆 v2.0 收官 (32/32 + Bonus 8/8) — 2026-05-21 ✅

**3 phase + 8 加分彩蛋 全部交付, 共 49 提交 (v1 archive 10 + v2 主线 39 + bonus 8 + polish 2)**。

---

## 🛠️ Polish round — 2026-05-21

### 提交 (1) — #26 调整 + #28 修复 + workflow 一键

**SHA**: `9b938300` · `(本提交)`

- **#26 补齐**: 补 `web/src/views/PresentationView.vue` + `components/SlideDeck.vue` + `services/tts.ts` + `router /present /edge` — 10 张幻灯片 + 键盘导航 + `R` 读稿, 未装 edge-tts 自动 fallback 浏览器 SpeechSynthesis。
- **#26 backend**: 补 `tts/TtsController` + `TtsProperties` + `application-tts.yml`, ProcessBuilder 外调 edge-tts CLI, 503 透明返。
- **#28 LocalChat.vue**: 修 Vue template 二重大括号被上游 URL 压缩吞掉 — 全部改 `v-text` / `v-bind` 形式。
- **#25 deps**: package.json 加 `vue-i18n@^9` + optionalDeps `@xenova/transformers@^2.17`。
- **#31 workflow**: 加 `scripts/install-supply-chain-workflow.sh` 一键 sed 转换占位符并 cp 到 `.github/workflows/`, README 补详细说明。

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

**提交 SHA**: `b0337f56` + polish `(本提交)`

### 动机
SLSA Build L2 是 2025-2026 企业交付门禁, GitHub Dependency Submission API 需 CycloneDX SBOM。

### 设计要点
- **Syft anchore/sbom-action@v0** 生 CycloneDX JSON, artifact 90d。
- **Trivy aquasecurity/trivy-action@0.24.0** fs scan, SARIF 上 GitHub Security tab, severity CRITICAL/HIGH。
- **Cosign keyless** OIDC `token.actions.githubusercontent.com`, sign-blob 不需私钥, Rekor public ledger。
- tag v* 另走 build-and-sign-images job 对 backend/rag/web 3 个镜像 cosign sign + trivy image 扫。
- **路径 fallback**: `zhiqian/security/workflows-template/supply-chain.yml` + `scripts/install-supply-chain-workflow.sh` sed 转占位符自动 cp。

### 变更项
4 新文件 + polish 1 脚本:
- `zhiqian/security/workflows-template/supply-chain.yml`
- `zhiqian/security/{POLICY.md, sbom-attestation-template.json, README.md}`
- `scripts/install-supply-chain-workflow.sh` (polish)

### 验证
```bash
bash scripts/install-supply-chain-workflow.sh
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

5 新文件: `zhiqian/docs/{architecture/{00-overall,01-agent-pipeline,02-rag-retrieval}.md, comparison.md, innovations.md}`。8 大创新点, 6 维度 × 5 商业迁移产品对比。

---

## [v2-step-29] 2026-05-21 — Sakila / Chinook / Employees 一键导入

**提交 SHA**: `636cb9a8`

6 新文件: `zhiqian/deploy/datasets/{docker-compose.yml, bootstrap.sh, migrate-all.sh, README.md, seed/.gitkeep, seed/.gitignore}`。profile=datasets, mysql:5.7 + opengauss-lite:5.0, 含 ZhiQian vs pgloader benchmark。

---

## [v2-step-28] 2026-05-21 — transformers.js 端侧推理 (Phi-3.5-mini ONNX) + polish 修模板

**提交 SHA**: `afb66784` + polish `(本提交)`

3 新文件: `web/src/{composables/useLocalLlm.ts, views/LocalChat.vue, composables/README-local-llm.md}`。WebGPU 首选 + WASM 降级, q4 量化。**Polish**: LocalChat.vue 模板用 `v-text` 重写防 URL 压缩损坏。

---

## [v2-step-27] 2026-05-21 — Typst PDF 迁移报告渲染

**提交 SHA**: `3a3c608c`

8 新文件: `rag/app/reports/{__init__.py, typst_renderer.py, templates/migration-report.typ, README.md}` + `rag/app/api/reports.py` + `rag/app/main.py` 重写 + `backend ReportClient / ReportController`。Typst Rust 实现 编译<1s, 中文原生支持, 未装优雅 503。

---

## [v2-step-26] 2026-05-21 — 答辩演示模式 + edge-tts 代理 (polish 已补齐)

**提交 SHA**: `9b938300`

### 动机
7-track Demo 页 + TTS 调 edge-tts (Microsoft 免费高品质语音), 现场答辩可读屏 / 离线浏览皆可。

### 设计要点 (polish 补齐)
- **PresentationView + SlideDeck**: 10 张幻灯片覆盖定位 / 问题 / 架构 / 创新 (2 split) / Demo 路径 / 对比 / 供应链 / 路线 / Q&A; `← →` `Home/End` `Esc` `R` 键控制; HUD 进度条 + 朗读按钮。
- **services/tts.ts**: 前端调 `RAG /tts/speak`, blob 解码 audio, 未装 edge-tts 优雅 fallback `window.speechSynthesis`。
- **backend `TtsController`**: ProcessBuilder 外调 `edge-tts --voice zh-CN-XiaoxiaoNeural`, 20s 超时, profile=tts 启用。
- **router**: 新增 `/present` (无 layout 全屏) + `/edge` (走 MainLayout)。

### 变更项 (polish)
7 新文件:
- `web/src/views/PresentationView.vue`
- `web/src/components/SlideDeck.vue`
- `web/src/services/tts.ts`
- `web/src/router/index.ts` (重写加路由)
- `backend tts/{TtsController, TtsProperties, README}.java/md`
- `backend application-tts.yml`

### 验证
```bash
# 启 web 后访 http://localhost:5173/#/present
# 可选启 edge-tts: pip install edge-tts && SPRING_PROFILES_ACTIVE=tts ./mvnw spring-boot:run
```

---

## [v2-step-25] 2026-05-21 — 暗色主题 + vue-i18n 国际化 + polish 装依赖

**提交 SHA**: `643b8dcf` + polish `(本提交)`

9 新/改文件: `locales/{zh-CN, en-US, index}.ts` + `composables/useTheme.ts` + `styles/theme.css` + `components/{Theme, Locale}Switcher.vue` + `main.ts` 重写。**Polish**: package.json 加 `vue-i18n@^9` 真依赖 + optionalDeps `@xenova/transformers@^2.17.2`。

---

## 🟢 Phase 3 milestone (7/7) — 2026-05-21 ✅

**云原生 Kustomize + ArgoCD GitOps + KubeRay/vLLM + Debezium CDC + pgloader/MTK + MCP + A2A**。Phase 3 全 7 步完成, 共 14 个新 SHA。

## [v2-step-24] A2A AgentCard + tasks/send + sendSubscribe SSE — `984dd127`
## [v2-step-23] MCP Server 6 tools (sql_transpile / sql_explain / schema_analysis / risk_report / retrieve / migrate_query) — `0faa7d9d`
## [v2-step-22] pgloader / MTK / ZhiqianNative MigrationToolFactory.recommend — `54695192`
## [v2-step-21] Debezium 3.0 CDC (MySQL → Kafka → openGauss) — `d997f284`
## [v2-step-20] KubeRay RayService autoscale 1-4 + vLLM profile — `57323cb6`
## [v2-step-19] ArgoCD AppProject + dev/prod Application + bootstrap — `46274be6` + `11713498`
## [v2-step-18] Kustomize base + dev/prod overlays (pivot from Helm) — `9833e4dc` + `c5f375d5`

---

## 🟢 Phase 2 milestone (6/6) — 2026-05-21 ✅

LangGraph CRAG + GraphRAG + Temporal + Outlines + Cytoscape + JaCoCo 全部交付。

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
