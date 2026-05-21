# 智迁云枢 v2 升级路线图

## 总进度表 (32 提交)

### Phase 1 — 真 LLM + 真检索 (P0) — ✅ 11/11

| # | 提交 | 状态 |
| --- | --- | --- |
| 1 | docs(v2): 升级路线图基线 | ✅ |
| 2 | feat(backend): DeepSeek LLM 客户端 | ✅ |
| 3 | feat(backend): LLM 驱动迁移流水线 | ✅ |
| 4 | feat(rag): BGE-M3 + bge-reranker-v2-m3 | ✅ |
| 5 | feat(rag): Qdrant + RRF 三路混合 | ✅ |
| 6 | feat(rag): Late Chunking + 语义分块 | ✅ |
| 7 | feat(rag): Langfuse trace 全链 | ✅ |
| 8 | feat(backend): Langfuse Java SDK | ✅ |
| 9 | feat(rag): sqlglot 替 Jinja2 | ✅ |
| 10 | feat(web): Monaco SQL Diff | ✅ |
| 11 | test(rag): RAGAS + golden set 20 | ✅ |

### Phase 2 — Agent + GraphRAG — ⏳ 0/6

| # | 提交 | 状态 |
| --- | --- | --- |
| 12 | feat(rag): LangGraph Self-RAG→CRAG | ⏳ |
| 13 | feat(rag): GraphRAG 索引 CKG | ⏳ |
| 14 | feat(backend): Temporal worker | ⏳ |
| 15 | feat(rag): Outlines 受约束解码 | ⏳ |
| 16 | feat(web): Cytoscape.js CKG 可视化 | ⏳ |
| 17 | test(backend): Spring Boot Test ≥0.8 | ⏳ |

### Phase 3 — 云原生 + 真库 + 协议 — ⏳ 0/7

| # | 提交 | 状态 |
| --- | --- | --- |
| 18 | feat(deploy): Helm Chart | ⏳ |
| 19 | feat(deploy): ArgoCD + Kustomize | ⏳ |
| 20 | feat(deploy): KubeRay + vLLM | ⏳ |
| 21 | feat(backend): Debezium 3.0 CDC | ⏳ |
| 22 | feat(backend): pgloader / MTK 适配 | ⏳ |
| 23 | feat(rag): MCP Server | ⏳ |
| 24 | feat(backend): A2A 协议 | ⏳ |

### 加分彩蛋 — ⏳ 0/8

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

---

## Phase 1 milestone (11/11) — 2026-05-21 ✅

**完成能力**:
- 真 LLM (DeepSeek-V3.1/R1) 驱动 6 Agent 迁移浴水线
- 中文 SOTA 检索 (BGE-M3 + reranker + Qdrant 3-way RRF + semantic chunking)
- 双端 Langfuse 可观测 (Python SDK + Java RestClient)
- sqlglot AST SQL 转译 (替代 Jinja2 字符串拼接)
- Monaco SQL Diff Web 页面 (/sql-transpile)
- RAGAS 三层可衡量 (retrieval recall@5 ≥ 0.80 / transpile 8 case / qa keyword ≥ 50%)

**质量基线**:
- /transpile 响应 < 200ms (sqlglot 本地 AST)
- /retrieve p50 < 1s (本地 fallback)
- backend 全链 trace 可在 Langfuse 上看到 6 个 stage span + N 个 generation 子节点

---

## 决策日志

| 日期 | 决策 |
| --- | --- |
| 2026-05-21 | LLM = DeepSeek-V3.1 |
| 2026-05-21 | docker compose 主 + Helm 副 |
| 2026-05-21 | 公开数据 Sakila/CM/Employees |
| 2026-05-21 | RestClient 不用 Spring AI |
| 2026-05-21 | api-key 为空优雅降级 |
| 2026-05-21 | 复用 AgentGraph |
| 2026-05-21 | ML 依赖到 ml.txt + BUILD_ML |
| 2026-05-21 | embedding_dim 768→1024 |
| 2026-05-21 | Qdrant 走 docker profile=ml |
| 2026-05-21 | RRF k=60 |
| 2026-05-21 | Late Chunking 默认 semantic |
| 2026-05-21 | char→token 近似映射不依赖 offset_mapping |
| 2026-05-21 | Langfuse 不入 pydantic Settings, secret 不进日志 |
| 2026-05-21 | retriever.search 加 parent_trace 透传, 合并 trace 树 |
| 2026-05-21 | Java 走 RestClient + Public Ingestion API, 不引 Langfuse SDK 重依赖 |
| 2026-05-21 | ThreadLocal trace context 让 LLM generation 自动 attach 到当前 stage span |
| 2026-05-21 | sqlglot 不内置 opengauss, normalize_dialect() alias 到 postgres 生成器 (95% 同语法) |
| 2026-05-21 | explain_transpile() 不走 AST walk, 用 substring 探测函数名 避免 sqlglot API 不稳定 |
| 2026-05-21 | Monaco worker 走主线程 (getWorkerUrl=data: URL), 避免 vite worker plugin 配置 |
| 2026-05-21 | web /sql-transpile 直调 rag (CORS allow_origins=*), 不走 backend 代理 |
| 2026-05-21 | Vue 模板全面走 v-text/computed, 避免   被上游工具压缩 URL 替换 (复发于 #1) |
| 2026-05-21 | 测试依赖独立 requirements-test.txt, 避免 langchain/datasets 污染产品镜像 |
| 2026-05-21 | RAGAS 调 DeepSeek 走 OpenAI compatible (langchain-openai.ChatOpenAI), 零代码修改 |
| 2026-05-21 | recall@5 阈值 0.80, faithfulness/relevancy 阈值 0.50 (保守, Phase 2 GraphRAG 后可取高) |
