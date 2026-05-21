# CHANGELOG

## [v2-step-05] 2026-05-21 — Qdrant 向量库 + 三路混合检索 + RRF 融合

**对应提交**：`feat(rag): Qdrant vector store + true 3-way hybrid retrieval (BM25 + Dense + Sparse) with RRF`

### 动机
step 4 中 BGE-M3 已接入，但仅用在粗改造、检索路径仍是单走 BM25，BGE-M3 的 dense + sparse 能力被浪费。本步补齐「三路检索」：BM25 + Dense（1024 维余弦）+ Sparse（lexical_weights），用 RRF (k=60) 融合。

### 设计要点
- **Qdrant 独立服务**：qdrant/qdrant:v1.11.3 以 docker-compose profile `ml` 可选启动。默认 `docker compose up -d` 不启 Qdrant，启动时间不变。启动时：`docker compose --profile ml up -d`。
- **如果 qdrant-client 未装或 URL 不可达**，QdrantStore.available=false，HybridRetriever 自动退化到 BM25 单路。调用者 0 原代码修改。
- **RRF (Reciprocal Rank Fusion)**不依赖底层分数尺度，在三路合并场景下鲁棒。公式：`score(d) = Σ 1/(k + rank_i(d))`。
- **多路可观测**：/health 与 /query 响应体都多了 `capabilities` 节点，说明当前哪几路可用（bm25/dense/sparse/rerank）。每个返回 chunk 多了 `channels` 字段，示产该文档在各路上的排名。
- **Demo 自动入库**：HybridRetriever 启动时检测到 Qdrant 可用会自动把 6 条 demo 文档走一遍 BGE-M3 生成 dense+sparse 后 upsert 进去，免手动 ingest。幂等（同 id 不重入）。
- **真接入 /ingest /retrieve**：v1 是空壳，本步委托给 HybridRetriever.add() 与 .search()，返回体多了 capabilities。

### 变更项
新增：
- `rag/app/store/qdrant_store.py` — Qdrant 封装。dense + sparse 在同一 collection，lazy connect，三态可用性。
- `rag/app/store/rrf.py` — RRF 融合算子 (k=60)。

修改：
- `rag/app/pipelines/retriever.py` — HybridRetriever 加 dense+sparse 两路，三路走 RRF；capabilities() 接口；demo seed：
- `rag/app/api/ingest.py` — 真接入，委托给 retriever.add。
- `rag/app/api/retrieve.py` — 真接入，委托给 retriever.search。
- `rag/app/main.py` — 挂载 /ingest /retrieve 路由。dependency_overrides 连接全局 retriever。
- `rag/app/config.py` — 新增 use_qdrant / qdrant_url / qdrant_api_key / rrf_k。
- `deploy/docker-compose.yml` — 新增 qdrant 服务（profile=ml），rag 透传 RAG_USE_QDRANT/QDRANT_URL/RRF_K。
- `deploy/.env.example` — 新增 Qdrant 存档说明。

### 影响范围
- ✅ GET /health.capabilities 加 7 个字段（bm25/dense/sparse/rerank/qdrant_url/embed_model/rrf_k）
- ✅ POST /query 响应体多了 capabilities；chunks[*] 多了 rrf_score、channels（仅三路走时）
- ✅ POST /ingest、/retrieve 从空壳变成真接入
- ➖ 默认 docker compose up -d (不加 --profile ml) 仍仅启动 postgres/backend/rag/web，其中 rag 走 BM25 单路。启动时间不变。
- ➖ docker compose --profile ml up -d 会多起一个 qdrant 容器，需要额外 ~500MB 内存。
- ➖ 需同时 RAG_BUILD_ML=1（装 FlagEmbedding+torch）+ --profile ml（起 qdrant）才能走完整三路。任一缺失仍可用。

### 验证方式
```bash
# 0. 轻依赖（不启 Qdrant）
docker compose up -d --build rag
curl http://localhost:8001/health | jq .capabilities
# 期望: bm25=true, dense=false, sparse=false, rerank=false

# 1. 完整三路
export RAG_BUILD_ML=1
docker compose --profile ml up -d --build rag qdrant
# 等待几分钟拉模型。
curl http://localhost:8001/health | jq .capabilities
# 期望: bm25=true, dense=true, sparse=true, rerank=true, qdrant_url=http://qdrant:6333

# 2. 查询验证三路生效
curl -X POST http://localhost:8001/query -H 'Content-Type: application/json' \
  -d '{"question":"补丁 JDBC URL 该怎么改","top_k":3}' | jq '.chunks[].channels, .capabilities'
# 期望: doc-3 排靠前; channels 字段包含 0/1/2 三个键

# 3. 动态 ingest
curl -X POST http://localhost:8001/ingest -H 'Content-Type: application/json' \
  -d '{"docs":[{"id":"doc-7","text":"openGauss 不支持 MySQL 的 GROUP_CONCAT 函数，应使用 string_agg。","source":"opengauss/dialect-cheatsheet.md#group-concat","meta":{"category":"SQL_REWRITE"}}]}' | jq
# 期望: inserted=1, capabilities.docs=7
```

### 回滚
```bash
git revert <本 SHA>
docker compose --profile ml down -v qdrant   # 可选，清 qdrant 数据卷
docker compose up -d --build rag
```

---

## [v2-step-04] 2026-05-21 — BGE-M3 + bge-reranker-v2-m3

对应: `feat(rag): real BGE-M3 embedding + bge-reranker-v2-m3 cross-encoder`. 1024 维、Lazy load、重依赖拆到 requirements-ml.txt + BUILD_ML。

## [v2-step-03] 2026-05-21 — 真 LLM 驱动迁移流水线

6 个 Stage Agent。修复 Result.success→Result.ok。

## [v2-step-02] 2026-05-21 — DeepSeek-V3.1 LLM 接入

## [v2-step-01] 2026-05-21 — 升级路线图基线

---
## v1 关键提交归档
`6fa440f5` v1 final · `e434028b` v-text fix · `96f4709b` web full · `f738149d` Jinja2 fix · `177e3566` pom+SQL · `aefbd4fc` CKG · `7907a90c` JWT+SSE · `ac79f9bc` compose+Dockerfiles
