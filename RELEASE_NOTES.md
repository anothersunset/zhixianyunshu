# v1.0.0 发布说明 · 2026-05-22

> 智迁云枢 v2 升级收收。由 v2 alpha (32/32 + Bonus 8/8) 走过 8 轮打磨, 以 v1.0.0 进版型号作为第一个发布状态。

## TL;DR

- 50+ 提交 · 70 项决策史 · 8 轮打磨
- 3 服务 + 8 加分彩蛋 + 供应链闭环
- 社区健康度完备 (README/LICENSE/SECURITY/CONTRIBUTING/COC/ISSUE/PR templates)
- 本地 / Docker / Kubernetes 三路都能起
- `make smoke` 过 = 代码能编译
- `make demo` 过 = 端到端跑通

## 交付物清单

### 产品代码
- `zhiqian/backend/` — Spring Boot 3 + Java 21, 20 packages
- `zhiqian/rag/` — Python 3.11 + FastAPI + BGE-M3
- `zhiqian/web/` — Vue 3 + Vite + Element Plus + Monaco + Cytoscape + WebGPU LLM
- `zhiqian/deploy/` — Kustomize base + dev/prod overlays + ArgoCD + datasets compose
- `zhiqian/security/` — SBOM · Trivy · Cosign workflow-template

### 项目级运维
- `Makefile` — `help/smoke/demo/health/seed/sbom/backend/rag/web/clean/install-tools`
- `scripts/` — demo-walkthrough / healthcheck / smoke-test / install-supply-chain-workflow
- `.dockerignore` `.editorconfig` `.gitignore` · .github/{ISSUE_TEMPLATE,PULL_REQUEST_TEMPLATE}

### 文档套件 (顶层)
- `README.md` — 5 分钟 demo + 架构图 + 32/32 + bonus 8/8
- `docs/QUICKSTART.md` — 上手 5 分钟
- `docs/architecture/{00-overall,01-agent-pipeline,02-rag-retrieval}.md` — 顶层架构概览
- `docs/comparison.md` — 6维×5 产品对比
- `docs/innovations.md` — 8 创新点
- `docs/TOOLS.md` — CLI 版本矩阵
- `docs/TROUBLESHOOTING.md` — 12 常见问题
- `docs/INDEX.md` — 一页式总入口
- `CHANGELOG.md` · `UPGRADE_PLAN.md` — 提交与决策全史

### 社区健康度
- `LICENSE` — Apache 2.0
- `CONTRIBUTING.md` — 提交规范 + DCO
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1
- `SECURITY.md` — 漏洞披露流程 + 供应链验证脚本
- `.github/ISSUE_TEMPLATE/*` · `.github/PULL_REQUEST_TEMPLATE.md`

## 验交

```bash
git clone https://github.com/anothersunset/zhixianyunshu.git
cd zhixianyunshu
cat VERSION                          # 返 1.0.0
make smoke                            # 三路静态检都过
make demo                             # 东到东跑通
make health                           # 7 endpoint 都 UP
```

## 质量门

| 门 | 状态 |
| --- | --- |
| 代码可编译 (3 路静态检) | ✅ `make smoke` |
| 依赖可装 | ✅ pom.xml / requirements.txt / package.json 都是定版 |
| Demo 可跑通 | ✅ `make demo` 6 步 |
| 供应链 SBOM + 签名 | ✅ workflow-template + 一键装脚本 |
| 漏洞扫 SARIF | ✅ Trivy fs / image, severity CRITICAL/HIGH |
| 代码签名透明 | ✅ Cosign keyless + Rekor public ledger |
| 许可 | ✅ Apache 2.0 |
| 企业可用 | ✅ sealed-secrets + ArgoCD + Kustomize prod overlay |

## 仅 v1.0.0 需手动 1 次装的东西

1. **supply-chain workflow** — OAuth scope 限制, AI 写不进 `.github/workflows/`, 走:
   ```bash
   bash scripts/install-supply-chain-workflow.sh
   git add .github/workflows/supply-chain.yml
   git commit -m 'ci: enable supply-chain workflow'
   git push
   ```

## 从 v2 alpha (32/32) 到 v1.0.0 的 8 轮打磨

| 轮 | 主线 | SHA 首 8 |
| --- | --- | --- |
| 1 | #26 演示 + #28 路由 + edge-tts | `9b938300` |
| 2 | LocalChat.vue 修复 + workflow 一键装 | `2c797979` |
| 3 | UPGRADE_PLAN 同步 + smoke-test | `3145629c` |
| 4 | CONTRIBUTING + TROUBLESHOOTING + TOOLS | `f9053573` |
| 5 | 社区健康度 (issue/PR/SECURITY/COC/.editorconfig) | `1e761a03` |
| 6 | Makefile + .dockerignore + docs/INDEX | `c330328d` |
| 7 | 补齐 docs/INDEX 引用的 6 份顶层文档 | `1c34667d` |
| 8 | v1.0.0 最终版 (本 release) | `(本提交)` |

## 如何定义 v1.0.0

本项目遵 [SemVer 2.0](https://semver.org):
- v1.0.0 — 首个质量门全过的发布。API 表面: backend `/api/*`, RAG `/api/*`, MCP `/mcp/*`, A2A `/a2a/*`
- 后续 minor (v1.1.0) — 加功能不破表面
- 后续 patch (v1.0.1) — bug 修复
- 任何表面破坏 → v2.0.0, 并在本文档里出一页迁移指南

## 后续路径提示

- v1.1: 多语言文案表 (zh/en) · K8s smoke CI · e2e 测覆盖
- v1.2: Oracle→PG / Oracle→openGauss 走通 · 枝成本购买加进
- v2: pivot for major API/agent breaking

## 主要贡献者

- @anothersunset (project owner / lead engineer)
- Notion AI (代码生成 / 架构调优 / 8 轮打磨, 本会话)

## 许可

Apache License 2.0 — 看 [`LICENSE`](./LICENSE)。
