# 文档总索引

一纸看清提交史 / 决策史 / 全部文档走到那了。

## 🚪 入口

| 身份 | 最快路径 |
| --- | --- |
| 拉来看东西 | [`README.md`](../README.md) → 核心亮点 + 快速开始 + 评测口径 |
| 拉来看介绍书 | [`PROJECT_INTRODUCTION.md`](./PROJECT_INTRODUCTION.md) — 项目背景/动机完整版 |
| 拉来跑 demo | [`QUICKSTART.md`](./QUICKSTART.md) → [`scripts/demo-walkthrough.sh`](../scripts/demo-walkthrough.sh) 或 `make demo` |
| 拉来贡献 | [`CONTRIBUTING.md`](../CONTRIBUTING.md) + `make smoke` |
| 拉来报 bug | [Issues](https://github.com/anothersunset/zhixianyunshu/issues/new/choose) (先读 TROUBLESHOOTING) |
| 拉来看架构 | [`architecture/`](./architecture/) 三张图（总览 / Agent DAG / RAG 检索）+ `zhiqian/docs/` 详解 |
| 拉来报漏 | [`SECURITY.md`](../SECURITY.md) |

## 📐 设计与架构

- [**垂直领域 Agent 设计方法论**](./AGENT_DESIGN.md) — 五支柱框架 + 设计取舍 + 文献锚点（推荐首读）
- [总架构图](./architecture/00-overall.md)
- [Agent DAG](./architecture/01-agent-pipeline.md)
- [RAG 检索路](./architecture/02-rag-retrieval.md)
- [评测驱动开发体系](../eval/README.md)
- [同类产品对比](./comparison.md)
- [8 大创新点](./innovations.md)

## 🔧 运维与调试

- [CLI 工具矩阵](./TOOLS.md) — 要什么版 / 怎么装
- [Troubleshooting](./TROUBLESHOOTING.md) — 12 条常见问题
- [本地 Docker 部署说明书](../LOCAL_DEPLOY_GUIDE.md) — Windows/WSL2 环境 v1.0.4 时点踩坑记录

## 📦 子模块文档

- [`zhiqian/README.md`](../zhiqian/README.md) — 主产品 README
- [`zhiqian/backend/tts/README.md`](../zhiqian/backend/src/main/java/com/zhiqian/tts/README.md) — backend TTS 路由
- [`zhiqian/deploy/README.md`](../zhiqian/deploy/README.md) — Kustomize / ArgoCD / sealed-secrets
- [`zhiqian/security/README.md`](../zhiqian/security/README.md) — 供应链 + workflow-template

> backend / rag / web 三个子模块暂无独立 README；起动方式见 [QUICKSTART.md](./QUICKSTART.md) 与根 [Makefile](../Makefile)。

## 📜 提交史 · 决策史

- [`UPGRADE_PLAN.md`](../UPGRADE_PLAN.md) — 70 项状态 + Polish round 表 + 50 条决策日志
- [`CHANGELOG.md`](../CHANGELOG.md) — 提交明细（含 Unreleased：P0/P1 审计修复三轮 25 个提交）
- [开发日志总索引](../eval/docs/devlog-index.md) — 全部 devlog 分类索引 + 跨项目教训提炼
- [P0/P1 遗留问题核实与修复](./devlog-2026-07-09-p0-p1-audit.md) — 10 项外部审查逐条核实（3 处描述有出入）+ 修复记录
- [第二轮 P0/P1 加固](./devlog-2026-07-12-second-hardening-round.md) — 15 个提交 diff 复盘（六 Agent 链路统一 / 鉴权 / retrieval mode / 门禁）
- [SQL Server 方言支持](./devlog-2026-06-30-sqlserver-support.md)
- [失败学习闭环](./devlog-2026-06-24-failure-learning-loop.md)
- [`TEST_REPORT.md`](../TEST_REPORT.md) — 历史快照（2026-06-01 v1 时点部署测试，非当前状态）

## ⚖️ 社区

- [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) — Contributor Covenant 2.1
- [`LICENSE`](../LICENSE) — Apache 2.0

## 💡 运作谁

指默 (`make help` 包全):

```
make help          菜单
make smoke         提交前检
make demo          一键 demo
make health        验服务状态
make seed          只拉数据库
make sbom          生 SBOM
make backend       起 Spring Boot (8080)
make rag           起 FastAPI (8001)
make web           起 Vite dev (5173)
make clean         清成品产物
```
