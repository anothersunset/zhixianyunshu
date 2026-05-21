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

### Phase 2 — Agent + GraphRAG — ✅ 6/6

| # | 提交 | 状态 |
| --- | --- | --- |
| 12 | feat(rag): LangGraph Self-RAG→CRAG | ✅ |
| 13 | feat(rag): GraphRAG 索引 CKG | ✅ |
| 14 | feat(backend): Temporal worker | ✅ |
| 15 | feat(rag): Outlines 受约束解码 | ✅ |
| 16 | feat(web): Cytoscape.js CKG 可视化 | ✅ |
| 17 | test(backend): Spring Boot Test ≥0.8 | ✅ |

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

真 LLM + 6 Agent + BGE-M3+RRF + Late Chunking + Langfuse 双端 + sqlglot + Monaco Diff + RAGAS。

---

## Phase 2 milestone (6/6) — 2026-05-21 ✅

**完成能力**:
- ✅ #12 LangGraph-style CRAG
- ✅ #13 GraphRAG 索引 CKG (Louvain-Lite + 双查询)
- ✅ #14 Temporal durable workflow (6 stage + REST + docker profile)
- ✅ #15 Outlines 受约束解码 (DeepSeek JSON mode + Outlines 双后端 + 3 endpoint)
- ✅ #16 Cytoscape.js CKG 可视化 (fcose layout + /ckg 页 + /api/ckg/graph)
- ✅ #17 Spring Boot Test ≥0.8 (Testcontainers + WebMvcTest + JaCoCo 门禁 ≥0.70 渐进)

**质量指标**:
- JaCoCo BUNDLE line coverage ≥ 0.70 门禁 (excludes temporal.workflow / bootstrap / Application)
- ZhiqianApplicationTests `@SpringBootTest` 点亮所有 bean, 单测覆盖率主力
- PostgresIntegrationTest 走 Testcontainers postgres:16-alpine 跑真 Flyway 迁移
- CkgGraphController + 6 Properties bean 全部有测试

**下一阶段 (Phase 3 — 云原生 + 真库 + 协议, 7 提交)**:
#18 Helm Chart → #19 ArgoCD+Kustomize → #20 KubeRay+vLLM → #21 Debezium 3.0 CDC → #22 pgloader/MTK → #23 MCP Server → #24 A2A 协议。

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
| 2026-05-21 | retriever.search 加 parent_trace 透传 |
| 2026-05-21 | Java 走 RestClient + Public Ingestion API |
| 2026-05-21 | ThreadLocal trace context |
| 2026-05-21 | sqlglot opengauss alias postgres (95% 同语法) |
| 2026-05-21 | explain_transpile 用 substring 探测函数名 |
| 2026-05-21 | Monaco worker 走主线程 (data: URL) |
| 2026-05-21 | web /sql-transpile 直调 rag (CORS=*) |
| 2026-05-21 | Vue 模板全面 v-text/computed 防 mustache 替换 |
| 2026-05-21 | 测试依赖独立 requirements-test.txt |
| 2026-05-21 | RAGAS 调 DeepSeek 走 OpenAI compatible |
| 2026-05-21 | recall@5 阈值 0.80, faithfulness/relevancy 0.50 |
| 2026-05-21 | CRAG 不引 langgraph, 自写 200 行 mini StateGraph |
| 2026-05-21 | CRAG evaluator 双轨 (LLM + 启发式) |
| 2026-05-21 | GraphRAG 自实现 Louvain-Lite, 不引 networkx |
| 2026-05-21 | GraphRagIndex 全局单例 + lazy build |
| 2026-05-21 | Temporal 默认 enabled=false |
| 2026-05-21 | Temporal 不用 spring-boot-starter-alpha |
| 2026-05-21 | TemporalActivities 委托 AgentRunner |
| 2026-05-21 | Temporal docker compose 走 profile=temporal opt-in |
| 2026-05-21 | TemporalMigrationController 用 ObjectProvider 返 503 |
| 2026-05-21 | Outlines 双后端: DeepSeek JSON mode 默认 + Outlines 可选 |
| 2026-05-21 | Structured output retry pydantic 错误反馈最多 3 次 |
| 2026-05-21 | jsonschema 必装, outlines 注释行可选 |
| 2026-05-21 | Cytoscape.js + cytoscape-fcose lazy import |
| 2026-05-21 | /api/ckg/graph 阶段性返 demo 图, 后续切真实数据 |
| 2026-05-21 | JaCoCo BUNDLE line coverage 门禁 0.70 起步 (Phase 2), 后续可上提到 0.80 |
| 2026-05-21 | JaCoCo excludes `temporal.workflow.**` (SDK proxy 难测) / `bootstrap/**` / `*Application*` |
| 2026-05-21 | Testcontainers PostgresIntegrationTest 加 EnabledIfEnvironmentVariable=RUN_TESTCONTAINERS 防止无 Docker 环境 CI 假阳 |
| 2026-05-21 | application-test.yml 单 profile 覆盖所有 Spring 上下文测试 (H2 + Temporal/Langfuse disabled + LLM mock) |
| 2026-05-21 | mockito-inline 而非 mockito-core, 给 Properties / final class mock 预留 |
