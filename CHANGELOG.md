# CHANGELOG

> 说明: 以下为智迁云枢 v2 升级正式启动以来的完整提交记录。每步提交同步更新 `UPGRADE_PLAN.md` 状态表。

## [v2-step-09] 2026-05-21 — sqlglot AST 转译替代 Jinja2 字符串拼接

**提交 SHA**: `7bc3236e` (新增文件) + `4678b735` (接入主应用) + 本 SHA (文档)。

### 动机
v1 用 Jinja2 字符串拼接 'MySQL 函数 → openGauss 函数',遇到 `DATE_FORMAT(t, '%Y-%m')` 含参数函数、嵌套 SELECT、别名 都会坏。答辩现场被问 'IFNULL(IFNULL(a,b),c) 你这德性能脱出来吗' 是明显扣分点。

### 设计要点
- sqlglot 是 Tobiko Data 纯 Python AST 库,Github 6k⭐,零依赖,~2MB。
- openGauss = postgres 别名: `normalize_dialect()` 把 opengauss/gauss/pg/postgresql 全部 alias 到 postgres (95% 同语法)。
- `explain_transpile()` 返回原/后 SQL + 中文变动说明。
- 两个独立端点: `POST /transpile` + `POST /transpile/batch`,都含 Langfuse trace。
- validation.py 向后兼容增强: SQL_REWRITE/DIALECT 路径自动 transpile,注入模板上下文。

### 变更项
- 新增: `rag/app/core/sql_transpiler.py`, `rag/app/api/transpile.py`
- 修改: `rag/app/main.py` (version 0.6.0,注册 router,/health 报 sqlglot_version), `rag/app/pipelines/validation.py` (注入 transpile_info), `rag/requirements.txt` (+sqlglot==25.16.1)

### 验证
```bash
curl -s http://localhost:8001/health | jq '.capabilities.sqlglot_version'
# => "25.16.1"
curl -s -X POST http://localhost:8001/transpile -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT IFNULL(a,b) FROM t LIMIT 5,10","target":"opengauss"}' | jq '.target'
# => "SELECT COALESCE(a, b) FROM t LIMIT 10 OFFSET 5"
```

### 回滚
`git revert <本 SHA>` → /transpile* 404; validation 退回纯 Jinja2。

---

## [v2-step-08] 2026-05-21 — Langfuse Java 客户端 + backend 全链埋点

**提交 SHA**: `1ca293a2`

### 动机
#7 为 rag 端加了 trace,但 backend 迁移流水线(6 agents × 多次 LLM 调用)才是核心路径。与 rag 端全面对称。

### 设计要点
- **零额外依赖**: Spring 6 原生 RestClient 直调 Public Ingestion API,不引 SDK。
- **ThreadLocal trace context**: AgentRunner bind/unbind,DeepSeekLlmClient 自动 attach,业务代码不传 traceId。
- **完全可选**: keys 留空 → `TraceHandle.NOOP` 零开销。
- **异步上报**: single-thread daemon executor,@PreDestroy 优雅关闭。
- **trace 树**: task.migration (root) → 01-analyzer:span → llm.chat:generation → ...

### 变更项
新增 4 个类: `LangfuseProperties` / `LangfuseConfig` / `LangfuseClient` / `TraceHandle`。
修改: `LlmClientFactory` (注入 LangfuseClient), `DeepSeekLlmClient` (callModel+genName), `AgentRunner` (run+parentTrace 重载), `TaskExecutionService` (起 root trace),`application.yml` (+app.langfuse), `docker-compose.yml` (backend env)。

### 验证
```bash
docker logs zhiqian-backend | grep '\[langfuse\]'
# disabled: [langfuse] disabled (set app.langfuse.public-key/secret-key to enable)
# enabled:  [langfuse] enabled host=https://cloud.langfuse.com (Public Ingestion API)
```

### 回滚
`git revert <SHA>` → 如业务玩犱 LangfuseClient 被移,临时可添空 bean。

---

## [v2-step-07] 2026-05-21 — Langfuse rag 端全链 trace

**提交 SHA**: `ceb27034`

### 动机
6 路检索混合 + critique 黑箱化,调试难。

### 设计要点
- Langfuse Python SDK 2.50.0,~3MB,入 requirements.txt。
- `core/observability.py`: LangfuseClient + _ActiveTrace + _ActiveSpan + _Noop。lazy init,keys 空 → disabled。
- /query trace 含 6 子 span: rewrite / bm25.search / bge.encode_query / qdrant.dense / qdrant.sparse / rrf.merge / rerank.cross_encoder / critique。
- /ingest + /retrieve_api 同样包 trace。
- /health.capabilities 报 langfuse_enabled + langfuse_host。

### 变更项
新增: `rag/app/core/observability.py`。
修改: retriever.py (search+parent_trace), main.py (/query trace), ingest.py + retrieve.py (包 trace), requirements.txt (+langfuse==2.50.0), docker-compose.yml (3 LANGFUSE_*), `.env.example`。

### 验证
`curl http://localhost:8001/health | jq '.capabilities.langfuse_enabled'`

---

## [v2-step-06] 2026-05-21 — Late Chunking + 语义分块

**提交 SHA**: `4670edd5`

### 动机
固定长 chunk 破坏上下文,影响检索质量。

### 设计要点
- `core/chunker.py`: `LateChunker` (先 embed 全文再切) + `SemanticChunker` (相邻句向量余弦相似度 < threshold 则切)。
- `pick_chunker(strategy)` 工厂 → retriever / ingest 复用。
- 环境变量: `RAG_CHUNK_STRATEGY=semantic`, `RAG_CHUNK_SIM_THRESHOLD=0.62`。

### 变更项
新增: `rag/app/core/chunker.py`。修改: ingest.py (调 chunker), retriever.py (ingest 同步), settings.py, .env.example。

---

## [v2-step-05] 2026-05-21 — Qdrant + 3 路 RRF 混合检索

**提交 SHA**: `104381a8`

### 动机
单路 BM25 召回低,单路向量语义走偏。RRF (Reciprocal Rank Fusion) 是业界公认 SOTA 融合算法。

### 设计要点
- `core/qdrant_store.py`: Qdrant 1.11.3 (docker profile=ml),dense + sparse collection。
- `core/fusion.py`: RRF k=60。
- HybridRetriever 3 路: BM25 + Qdrant dense + Qdrant sparse → RRF → reranker。

### 变更项
新增: `rag/app/core/{qdrant_store,fusion}.py`, `rag/app/api/{ingest,retrieve}.py`。修改: retriever.py (3 路 + RRF), docker-compose.yml (+qdrant service)。

---

## [v2-step-04] 2026-05-21 — BGE-M3 + bge-reranker-v2-m3 (中文 SOTA 检索)

**提交 SHA**: `d6b4ac58`

### 动机
全凭 Jaccard + jieba 在中文代码机检索质量不够。

### 设计要点
- BGE-M3: 多语言 + dense+sparse+colbert 三路一起出。
- bge-reranker-v2-m3: 跨编码器,随取后出。
- 重依赖拆到 `requirements-ml.txt`,docker build --build-arg BUILD_ML=1 才装。
- HF_ENDPOINT=https://hf-mirror.com 默认走镜像。

### 变更项
新增: `rag/app/core/{bge_m3_embedder,cross_encoder_reranker}.py`, `rag/requirements-ml.txt`。修改: retriever.py, Dockerfile, docker-compose.yml。

---

## [v2-step-03] 2026-05-21 — LLM 驱动 6 Agent 迁移流水线

**提交 SHA**: `8d4fff1d`

### 动机
v1 主流程全是 mock 限制代码,无真 LLM 介入。

### 设计要点
- 6 个 Agent: SchemaAnalyzer / ContextRetriever / SqlReasoner / SqlPatcher / SqlCritic / ReportSummarizer。
- AgentGraph 串联, AgentRunner 逐节点执行, 输出 _model/_confidence/_real 元数据。
- TaskExecutionService SSE 事件: step (JSON) + progress。
- Bug fix: LlmController `Result.success` → `Result.ok` (Result 只有 ok/fail)。

### 变更项
新增包: `agent`, `agent.tools`。修改: TaskExecutionService, AsyncConfig, TaskController。

---

## [v2-step-02] 2026-05-21 — DeepSeek LLM 客户端

**提交 SHA**: `790b10f2`

### 动机
选 DeepSeek-V3.1 / R1 作为主 LLM (低成本中文优势 SOTA)。

### 设计要点
- `llm.LlmClient` 接口 + `DeepSeekLlmClient` 实现 + `MockLlmClient` 降级。
- `LlmClientFactory` 按 app.llm.api-key 是否空选择 real/mock。
- 3 个端点: GET /api/llm/health, POST /api/llm/chat, POST /api/llm/reason (JWT)。
- 配置: app.llm.{provider,api-key,base-url,chat-model,reasoner-model,temperature,max-tokens,timeout-seconds}。

### 变更项
新增包: `llm`, `llm.dto`。修改: SecurityConfig (放 /api/llm/health), application.yml。

---

## [v2-step-01] 2026-05-21 — v2 升级路线图基线

**提交 SHA**: `913006c0`

### 动机
用户选「全量 + 加分彩蛋 (MCP/A2A/Typst PDF/WebGPU 端侧)」, 需先启动路线。

### 变更项
新增: `UPGRADE_PLAN.md` (Phase 1/2/3 + 加分 共 32 提交), `CHANGELOG.md`, `docs/v2-overview.md`。
