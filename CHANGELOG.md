# CHANGELOG

> 说明: 以下为智迁云枢 v2 升级正式启动以来的完整提交记录。每步提交同步更新 `UPGRADE_PLAN.md` 状态表。

---

## 🟢 Phase 1 milestone (11/11) — 2026-05-21

**RAG 主链路可交付**。包括: DeepSeek LLM 接入 + 6 Agent 迁移流水线 + BGE-M3+重排 + Qdrant+RRF + Late/Semantic Chunking + Langfuse 双端 trace + sqlglot AST 转译 + Monaco SQL Diff Web + RAGAS+golden set 衡量。

下一阶段 (Phase 2): LangGraph CRAG, GraphRAG, Temporal worker, Outlines 约束解码, Cytoscape CKG 可视化, Spring Boot Test 覆盖率 ≥0.8。

---

## [v2-step-11] 2026-05-21 — RAGAS + 20 条 golden set 三层可衡量

**提交 SHA**: `4f17463c`

### 动机
以前「每步动 RAG 都不知道质量是提升还是退化」。进入后续优化循环前, 必须先钒上可重复的衡量手段。

### 设计要点
- **三层测试**: test_retrieval (recall@5 ≥ 0.80, p50 < 1s, 无 LLM) / test_transpile (8 条 sqlglot 输出断言, 无网络) / test_ragas (faithfulness+answer_relevancy, DeepSeek 判官)。
- **依赖隔离**: requirements-test.txt 独立, 不污染产品镜像。包含 ragas / langchain-openai / datasets。
- **20 条 golden set JSONL**: 8 transpile + 6 retrieve + 6 qa, 覆盖函数映射 / JDBC / 分页 / 类型 / JSON / 事务。
- **Skipif**: 本地无 DEEPSEEK_API_KEY 不报错, CI 可点。
- **Fallback**: test_keyword_faithfulness_fallback 不需 LLM, 50% 阈值下限。

### 变更项
新增: `rag/tests/{__init__,conftest,test_retrieval,test_transpile,test_ragas}.py`, `rag/tests/data/golden_set.jsonl`, `rag/requirements-test.txt`, `rag/Makefile`。

### 验证
```bash
cd zhiqian/rag && pip install -r requirements-test.txt
make test-fast      # 本地 ~5s, 跑三层中前两层
make test-ragas     # ~30s, 需 DEEPSEEK_API_KEY
make coverage       # htmlcov/
```

### 回滚
`git revert <SHA>` → tests/ 目录清空, 产品代码不受影响。

---

## [v2-step-10] 2026-05-21 — Monaco SQL Diff Web 页面

**提交 SHA**: `6b3d3dec` (创建) + `ce3cbb0f` (修复与接入)

### 动机
#9 上线 /transpile API 后, 需一个能在浏览器里看 SQL Diff 转译效果的页面。VSCode 同款 Monaco Editor 是广认场 SOTA。

### 设计要点
- monaco-editor 0.50.0 依赖, 动态 import 仅在 /sql-transpile 路由 lazy load。
- 关闭 worker 要求 (getWorkerUrl 返 data: URL), 避免 vite worker plugin 配置。
- /sql-transpile 页: 源/目标方言下拉 + 示例按钮 + diff 面板 + 变动说明表格。
- api/transpile.ts 直接打 rag service (default http://localhost:8001), CORS 走通。
- **Bug fix**: batch1 推送时 Vue 模板里的 ` var ` 被上游工具替换成了压缩 URL 占位, batch2 改成 v-text 修复。

### 变更项
新增: `web/src/components/SqlDiffEditor.vue`, `web/src/views/SqlTranspile.vue`, `web/src/api/transpile.ts`。
修改: `web/package.json` (+monaco-editor + version 0.3.0), `web/src/router/index.ts` (+/sql-transpile), `web/src/layouts/MainLayout.vue` (+SQL 转译 菜单)。

### 验证
```bash
cd zhiqian/web && npm install && npm run dev
# 打开 http://localhost:5173/#/sql-transpile
# 示例 -> 转译 -> diff 双栏出 COALESCE / TO_CHAR / LIMIT N OFFSET M
```

### 回滚
`git revert <两个 SHA>` → 菜单项与路由移除; rag /transpile 仍可 CLI 调用。

---

## [v2-step-09] 2026-05-21 — sqlglot AST 转译替代 Jinja2 字符串拼接

**提交 SHA**: `7bc3236e` (新增文件) + `4678b735` (接入主应用) + `bde6b9a1` (文档)

### 动机
v1 用 Jinja2 字符串拼接 'MySQL 函数 → openGauss 函数', 遇到 `DATE_FORMAT(t, '%Y-%m')` 含参数函数、嵌套 SELECT、别名 都会坏。

### 设计要点
- sqlglot 是 Tobiko Data 纯 Python AST 库, 6k⭐, 零依赖, ~2MB。
- openGauss = postgres 别名: normalize_dialect() alias 到 postgres (95% 同语法)。
- explain_transpile() 返原/后 SQL + 中文变动说明。
- 两个独立端点: POST /transpile + /transpile/batch, 都含 Langfuse trace。
- validation.py SQL_REWRITE/DIALECT 路径自动 transpile, 注入模板上下文。

### 变更项
新增: `rag/app/core/sql_transpiler.py`, `rag/app/api/transpile.py`。
修改: `rag/app/main.py` (0.6.0, 注册 router, /health 报 sqlglot_version), `rag/app/pipelines/validation.py`, `rag/requirements.txt` (+sqlglot==25.16.1)。

### 验证
```bash
curl -s http://localhost:8001/health | jq '.capabilities.sqlglot_version'  # 25.16.1
curl -s -X POST http://localhost:8001/transpile -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT IFNULL(a,b) FROM t LIMIT 5,10","target":"opengauss"}' | jq '.target'
# => "SELECT COALESCE(a, b) FROM t LIMIT 10 OFFSET 5"
```

---

## [v2-step-08] 2026-05-21 — Langfuse Java 客户端 + backend 全链埋点

**提交 SHA**: `1ca293a2`

### 动机
#7 为 rag 端加了 trace, backend 迁移流水线(6 agents × 多次 LLM)才是核心路径。与 rag 端全面对称。

### 设计要点
- **零额外依赖**: Spring 6 原生 RestClient 直调 Public Ingestion API, 不引 SDK。
- **ThreadLocal trace context**: AgentRunner bind/unbind, DeepSeekLlmClient 自动 attach。
- **完全可选**: keys 留空 → TraceHandle.NOOP 零开销。
- **异步上报**: single-thread daemon executor, @PreDestroy 优雅关闭。

### 变更项
新增 4 个类: `LangfuseProperties` / `LangfuseConfig` / `LangfuseClient` / `TraceHandle`。
修改: `LlmClientFactory`, `DeepSeekLlmClient`, `AgentRunner`, `TaskExecutionService`, `application.yml`, `docker-compose.yml`。

### 验证
```bash
docker logs zhiqian-backend | grep '\[langfuse\]'
# disabled: [langfuse] disabled (set app.langfuse.public-key/secret-key to enable)
# enabled:  [langfuse] enabled host=https://cloud.langfuse.com (Public Ingestion API)
```

---

## [v2-step-07] 2026-05-21 — Langfuse rag 端全链 trace

**提交 SHA**: `ceb27034`

### 动机
6 路检索混合 + critique 黑箱化, 调试难。

### 设计要点
- Langfuse Python SDK 2.50.0。lazy init, keys 空 → disabled。
- /query trace 含 6 子 span: rewrite / bm25.search / bge.encode_query / qdrant.dense / qdrant.sparse / rrf.merge / rerank.cross_encoder / critique。
- /ingest + /retrieve_api 同样包 trace。
- /health.capabilities 报 langfuse_enabled + langfuse_host。

### 变更项
新增: `rag/app/core/observability.py`。修改: retriever.py, main.py, ingest.py, retrieve.py, requirements.txt, docker-compose.yml, .env.example。

---

## [v2-step-06] 2026-05-21 — Late Chunking + 语义分块

**提交 SHA**: `4670edd5`

### 动机
固定长 chunk 破坏上下文, 影响检索质量。

### 设计要点
- LateChunker (先 embed 全文再切) + SemanticChunker (相邻句余弦 < threshold)。
- pick_chunker(strategy) 工厂 → retriever / ingest 复用。
- env: `RAG_CHUNK_STRATEGY=semantic`, `RAG_CHUNK_SIM_THRESHOLD=0.62`。

---

## [v2-step-05] 2026-05-21 — Qdrant + 3 路 RRF 混合检索

**提交 SHA**: `104381a8`

### 动机
单路 BM25 召回低, 单路向量语义走偏。RRF 是业界公认 SOTA 融合。

### 设计要点
- Qdrant 1.11.3 (docker profile=ml), dense + sparse collection。
- RRF k=60。
- HybridRetriever 3 路: BM25 + Qdrant dense + Qdrant sparse → RRF → reranker。

---

## [v2-step-04] 2026-05-21 — BGE-M3 + bge-reranker-v2-m3 (中文 SOTA)

**提交 SHA**: `d6b4ac58`

### 动机
全凭 Jaccard + jieba 在中文代码机检索质量不够。

### 设计要点
- BGE-M3 多语言 + dense+sparse+colbert 三路。
- bge-reranker-v2-m3 跨编码器后出。
- requirements-ml.txt + docker build --build-arg BUILD_ML=1。
- HF_ENDPOINT=https://hf-mirror.com 默认走镜像。

---

## [v2-step-03] 2026-05-21 — LLM 驱动 6 Agent 迁移流水线

**提交 SHA**: `8d4fff1d`

### 动机
v1 主流程全是 mock 限制代码。

### 设计要点
- 6 Agent: SchemaAnalyzer / ContextRetriever / SqlReasoner / SqlPatcher / SqlCritic / ReportSummarizer。
- AgentGraph 串联, AgentRunner 逐节点, 输出 _model/_confidence/_real 元数据。
- TaskExecutionService SSE: step (JSON) + progress。
- Bug fix: LlmController Result.success → Result.ok。

---

## [v2-step-02] 2026-05-21 — DeepSeek LLM 客户端

**提交 SHA**: `790b10f2`

### 动机
DeepSeek-V3.1 / R1 (低成本中文优势 SOTA)。

### 设计要点
- LlmClient 接口 + DeepSeekLlmClient + MockLlmClient 降级。
- LlmClientFactory 按 api-key 是否空选 real/mock。
- /api/llm/{health,chat,reason} 三个端点。

---

## [v2-step-01] 2026-05-21 — v2 升级路线图基线

**提交 SHA**: `913006c0`

创建 UPGRADE_PLAN.md / CHANGELOG.md / docs/v2-overview.md, Phase 1/2/3 + 加分 共 32 提交路线。
