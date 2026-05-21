# docs/

项目设计与运维文档集。快速入入口 → 根 README.md 与 CHANGELOG.md。

## 架构与设计

| 文档 | 主题 |
| --- | --- |
| `architecture/00-overall.md` | 总架构 — 6 层 mermaid + MCP/A2A/CDC/KubeRay 集成点 |
| `architecture/01-agent-pipeline.md` | 6 Agent DAG + LangGraph CRAG 接口 |
| `architecture/02-rag-retrieval.md` | BGE-M3 三路 + RRF + Late Chunking + GraphRAG |
| `comparison.md` | 同类产品 6 维度 × 5 产品对比 |
| `innovations.md` | 8 大创新点 |

## 运维与调试

| 文档 | 主题 |
| --- | --- |
| `TOOLS.md` | CLI 版本矩阵 + 一键装 (macOS / Ubuntu) |
| `TROUBLESHOOTING.md` | 12 条常见问题 + 定位/修复 |

## 贡献与社区

| 文档 | 主题 |
| --- | --- |
| `../CONTRIBUTING.md` | 提交规范 + branch + PR + DCO |
| `../CODE_OF_CONDUCT.md` | Contributor Covenant 2.1 |
| `../SECURITY.md` | 漏洞披露 + 供应链验证 |

## 参考脚本

| 脚本 | 用途 |
| --- | --- |
| `../scripts/demo-walkthrough.sh` | 6 步一键拉 demo |
| `../scripts/healthcheck.sh` | 7 endpoint 验状态 |
| `../scripts/smoke-test.sh` | 三路静态检 |
| `../scripts/install-supply-chain-workflow.sh` | 一键装供应链 CI |

## 设计决策与提交史

- 决策日志: `../UPGRADE_PLAN.md` (70 条)
- 提交明细: `../CHANGELOG.md`
