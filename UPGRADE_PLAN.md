# 智迁云枢 v2 升级路线图

> `CHANGELOG.md` 是逐项执行日志。本文件是全貌 + 决策。

## 决策摘要 (2026-05-21)

| 维度 | 决策 | 备注 |
| --- | --- | --- |
| 升级范围 | Phase 1+2+3 + 加分彩蛋 | 冲奖 + 论文 |
| LLM Provider | DeepSeek-V3.1 (OpenAI 兼容) | |
| API Key | `.env` 占位 | |
| 部署主 | docker compose | |
| 部署副 | Helm + Kustomize | |
| 真实样本 | Sakila + Classic Models + Employees | |
| 品牌化 | 完整 + 答辩演示模式 | |
| 节奏 | 多提交·独立验证·可追溯 | |
| 仓库 | `anothersunset/zhixianyunshu` `main` | |

## 提交规范
标题：`type(scope): 改了什么 — 为什么 (影响)`
正文必含：动机 / 变更项 / 影响 / 验证 / 回滚

## 总进度表（32 提交）

### Phase 1 — 真 LLM + 真检索（P0）

| # | 提交 | 状态 |
| --- | --- | --- |
| 1 | docs(v2): 升级路线图基线 | ✅ |
| 2 | feat(backend): DeepSeek LLM 客户端 | ✅ |
| 3 | feat(backend): LLM 驱动迁移流水线 | ✅ |
| 4 | feat(rag): BGE-M3 + bge-reranker-v2-m3 | ✅ |
| 5 | feat(rag): Qdrant 向量库 + 混合检索 | ⏳ |
| 6 | feat(rag): Late Chunking + 语义分块 | ⏳ |
| 7 | feat(rag): Langfuse trace 全链 | ⏳ |
| 8 | feat(backend): Langfuse Java SDK | ⏳ |
| 9 | feat(rag): sqlglot 替 Jinja2 | ⏳ |
| 10 | feat(web): Monaco SQL Diff | ⏳ |
| 11 | test(rag): RAGAS + golden set 20 | ⏳ |

### Phase 2 — Agent + GraphRAG（P1）

| # | 提交 | 状态 |
| --- | --- | --- |
| 12 | feat(rag): LangGraph Self-RAG→CRAG | ⏳ |
| 13 | feat(rag): GraphRAG 索引 CKG | ⏳ |
| 14 | feat(backend): Temporal worker | ⏳ |
| 15 | feat(rag): Outlines 受约束解码 | ⏳ |
| 16 | feat(web): Cytoscape.js CKG 可视化 | ⏳ |
| 17 | test(backend): Spring Boot Test ≥0.8 | ⏳ |

### Phase 3 — 云原生 + 真库 + 协议（P2）

| # | 提交 | 状态 |
| --- | --- | --- |
| 18 | feat(deploy): Helm Chart | ⏳ |
| 19 | feat(deploy): ArgoCD + Kustomize | ⏳ |
| 20 | feat(deploy): KubeRay + vLLM | ⏳ |
| 21 | feat(backend): Debezium 3.0 CDC | ⏳ |
| 22 | feat(backend): pgloader / MTK 适配 | ⏳ |
| 23 | feat(rag): MCP Server | ⏳ |
| 24 | feat(backend): A2A 协议 | ⏳ |

### 加分彩蛋（P3）

| # | 提交 | 状态 |
| --- | --- | --- |
| 25 | feat(web): 暗色 + i18n | ⏳ |
| 26 | feat(web): 答辩演示模式 + edge-tts | ⏳ |
| 27 | feat(reports): Typst PDF | ⏳ |
| 28 | feat(web): transformers.js 端侧 | ⏳ |
| 29 | feat(deploy): 公开数据集一键导入 | ⏳ |
| 30 | docs: 论文架构 + 对比表 | ⏳ |
| 31 | chore: SBOM + Cosign + Trivy | ⏳ |
| 32 | docs: 最终 README + 脚本 | ⏳ |

## 决策日志

| 日期 | 决策 | 决策人 | 理由 |
| --- | --- | --- | --- |
| 2026-05-21 | 全量升级 + 彩蛋 | lee fanwei | 冲奖 |
| 2026-05-21 | LLM 选 DeepSeek-V3.1 | lee fanwei | 性价比 |
| 2026-05-21 | docker compose 为主 | lee fanwei | 本地 30s |
| 2026-05-21 | Sakila/CM/Employees | lee fanwei | 合规 |
| 2026-05-21 | RestClient 不用 Spring AI | AI 负责人 | 避免 Boot 升级 |
| 2026-05-21 | api-key 为空优雅降级 | AI 负责人 | 零配启动 |
| 2026-05-21 | 复用 AgentGraph | AI 负责人 | LangGraph 平滑 |
| 2026-05-21 | ML 依赖拆到 ml.txt + BUILD_ML | AI 负责人 | 轻重可选，默认不装 torch |
| 2026-05-21 | embedding_dim 768→1024 | AI 负责人 | BGE-M3 原生，退化 hash 也 padding 到 1024 |
