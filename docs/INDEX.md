# 文档总索引

一纸看清 50 多个提交 / 70 项决策 / 10 块产品走到那了。

## 🚪 入口

| 身份 | 最快路径 |
| --- | --- |
| 拉来看东西 | [`README.md`](../README.md) → §0 产品一句话 + 5 分钟 demo |
| 拉来跑 demo | [`scripts/demo-walkthrough.sh`](../scripts/demo-walkthrough.sh) 或 `make demo` |
| 拉来贡献 | [`CONTRIBUTING.md`](../CONTRIBUTING.md) + `make smoke` |
| 拉来报 bug | [Issues](https://github.com/anothersunset/zhixianyunshu/issues/new/choose) (先读 TROUBLESHOOTING) |
| 拉来看架构 | `zhiqian/docs/architecture.md` + `architecture/` 5 张图 |
| 拉来报漏 | [`SECURITY.md`](../SECURITY.md) |

## 📐 设计与架构

- [总架构图](./architecture/00-overall.md)
- [Agent DAG](./architecture/01-agent-pipeline.md)
- [RAG 检索路](./architecture/02-rag-retrieval.md)
- [同类产品对比](./comparison.md)
- [8 大创新点](./innovations.md)

## 🔧 运维与调试

- [CLI 工具矩阵](./TOOLS.md) — 要什么版 / 怎么装
- [Troubleshooting](./TROUBLESHOOTING.md) — 12 条常见问题

## 📦 子模块文档

- [`zhiqian/README.md`](../zhiqian/README.md) — 主产品 README
- [`zhiqian/backend/README.md`](../zhiqian/backend/README.md) — Spring Boot 起动 / DTO / interfaces
- [`zhiqian/backend/tts/README.md`](../zhiqian/backend/src/main/java/com/zhiqian/tts/README.md) — #26 backend 路由
- [`zhiqian/rag/README.md`](../zhiqian/rag/README.md) — FastAPI 起动 / RAG 参数
- [`zhiqian/web/README.md`](../zhiqian/web/README.md) — Vite + Vue 3 + WebGPU
- [`zhiqian/deploy/README.md`](../zhiqian/deploy/README.md) — Kustomize / ArgoCD / sealed-secrets
- [`zhiqian/security/README.md`](../zhiqian/security/README.md) — #31 供应链 + workflow-template

## 📜 提交史 · 决策史

- [`UPGRADE_PLAN.md`](../UPGRADE_PLAN.md) — 70 项状态 + Polish round 表 + 50 条决策日志
- [`CHANGELOG.md`](../CHANGELOG.md) — 50+ 提交明细 (包子 SHA · message · 动机)

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
