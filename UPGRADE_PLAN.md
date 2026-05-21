# 智迁云枢 v2 升级路线图

> 本文件是 v2 全量升级的**导航图**与**决策记录**。`CHANGELOG.md` 是逐项执行日志。

## 决策摘要 (2026-05-21)

| 维度 | 决策 | 备注 |
| --- | --- | --- |
| 升级范围 | Phase 1+2+3 + 加分彩蛋 | 冲奖项 + 论文 |
| LLM Provider | DeepSeek-V3.1 (OpenAI 兼容) | 可切 Qwen3 / GLM-4.5 |
| API Key 策略 | `.env` 占位,用户自填 | 不进仓库 |
| 部署主路径 | docker compose | 本地 30 秒可跑 |
| 部署副路径 | Helm + Kustomize | K8s GitOps |
| 真实样本 | Sakila + Classic Models + Employees | MySQL 公开样本 |
| 前端品牌化 | 完整 + 答辩演示模式 | + edge-tts 播报 |
| 交付节奏 | 多提交 · 每个独立验证 · 可追溯 | 优先质量 |
| 仓库分支 | `anothersunset/zhixianyunshu` `main` | 直推 |

## 提交规范
标题：`type(scope): 改了什么 — 为什么 (影响)`
正文必含：动机 / 变更项 / 影响 / 验证 / 回滚

## 总进度表（32 提交）

### Phase 1 — 真 LLM + 真检索（P0）

| # | 提交 | 状态 | 影响 |
| --- | --- | --- | --- |
| 1 | docs(v2): 升级路线图基线 | ✅ | 导航 |
| 2 | feat(backend): DeepSeek LLM 客户端 | ✅ | 真 LLM 能力 |
| 3 | feat(backend): LLM 驱动迁移流水线 | ✅ | SSE 变真 |
| 4 | feat(rag): BGE-M3 + bge-reranker-v2-m3 | ⏳ | 检索质量阶跃 |
| 5 | feat(rag): Qdrant 向量库 + 混合检索 | ⏳ | 召回+30% |
| 6 | feat(rag): Late Chunking + 语义分块 | ⏳ | 长文档不丢语义 |
| 7 | feat(rag): Langfuse trace 全链路 | ⏳ | 可观测性 |
| 8 | feat(backend): Langfuse Java SDK + traceId | ⏳ | 跨服务追踪 |
| 9 | feat(rag): sqlglot 替 Jinja2 | ⏳ | AST 转译正确性 |
| 10 | feat(web): Monaco SQL Diff | ⏳ | 可视化对比 |
| 11 | test(rag): RAGAS 评测 + golden set 20 条 | ⏳ | 量化质量 |

### Phase 2 — Agent + GraphRAG（P1）

| # | 提交 | 状态 |
| --- | --- | --- |
| 12 | feat(rag): LangGraph Self-RAG → CRAG | ⏳ |
| 13 | feat(rag): GraphRAG 索引 CKG | ⏳ |
| 14 | feat(backend): Temporal worker | ⏳ |
| 15 | feat(rag): Outlines 受约束解码 | ⏳ |
| 16 | feat(web): Cytoscape.js CKG 可视化 | ⏳ |
| 17 | test(backend): Spring Boot Test 覆盖率 ≥ 80% | ⏳ |

### Phase 3 — 云原生 + 真库 + 协议（P2）

| # | 提交 | 状态 |
| --- | --- | --- |
| 18 | feat(deploy): Helm Chart | ⏳ |
| 19 | feat(deploy): ArgoCD + Kustomize | ⏳ |
| 20 | feat(deploy): KubeRay + vLLM 可选 | ⏳ |
| 21 | feat(backend): Debezium 3.0 CDC | ⏳ |
| 22 | feat(backend): pgloader / openGauss MTK | ⏳ |
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
| 30 | docs: 论文架构图 + 对比表 | ⏳ |
| 31 | chore: SBOM + Cosign + Trivy | ⏳ |
| 32 | docs: 最终 README + 演示脚本 | ⏳ |

## 决策日志

| 日期 | 决策 | 决策人 | 理由 |
| --- | --- | --- | --- |
| 2026-05-21 | 全量升级 + 彩蛋 | lee fanwei | 冲奖 |
| 2026-05-21 | LLM 选 DeepSeek-V3.1 | lee fanwei | 性价比 + 中文 SOTA |
| 2026-05-21 | docker compose 为主 | lee fanwei | 本地 30s |
| 2026-05-21 | 公开数据集 Sakila/CM/Employees | lee fanwei | 合规 |
| 2026-05-21 | LLM 不引 Spring AI、用 RestClient | AI 负责人 | 避免 Boot 升级 |
| 2026-05-21 | api-key 为空优雅降级 | AI 负责人 | 零配启动 |
| 2026-05-21 | 复用 AgentGraph、不重写 Stage 接口 | AI 负责人 | Phase 2 LangGraph 接入平滑 |
| 2026-05-21 | TaskSseDemoEmitter 保留为谐接 | AI 负责人 | 保留回滚错 |
