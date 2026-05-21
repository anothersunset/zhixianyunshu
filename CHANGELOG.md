# CHANGELOG

## [v2-step-07] 2026-05-21 — Langfuse 全链路埋点 (rag 端)

**对应提交**: `feat(rag): Langfuse 全链路埋点 — 检索/查询/入库每一步皆可视化`

### 动机
step 4-6 后真 LLM + BGE-M3 + 三路检索 + Late Chunking 都已就绪,链路深得用户/答辩评委看不见每一步的耗时与中间结果。Langfuse 是当前最成熟的 LLM 应用观测平台,trace/span 模型恰好契合 RAG 多步管线;论文中可直接截图作为系统说明图。

### 设计要点
- **完全可选**: 不配 LANGFUSE_PUBLIC_KEY/SECRET_KEY 时行为完全不变,只多 1 条 INFO 日志说明 disabled。
- **调用代码恒等**: 业务代码不分 enabled/disabled,统一 `with lf.trace(...) as tr: with tr.span(...) as sp:`,disabled 路径走 _NoopTrace/_NoopSpan,无网络无序列化。
- **trace 透传**: retriever.search() 新增 `parent_trace` 参数,/query 自起 `rag.query` 后透传给 retriever,合并成一棵 trace 树而不是两个并列 trace。
- **secret 不入 pydantic**: LANGFUSE_PUBLIC/SECRET 直接 os.getenv,避免被 BaseSettings repr 打印到日志。
- **lazy init**: LangfuseClient 首次访问 .available 才尝试 import + 连接,启动时间影响 < 0.3s。

### 变更项
新增:
- `rag/app/core/observability.py` — LangfuseClient + _ActiveTrace + _ActiveSpan + _NoopTrace + _NoopSpan,全局单例 get_langfuse()。

修改:
- `rag/app/pipelines/retriever.py` — search() 新增 parent_trace 参数;6 段 span: bm25.search / bge.encode_query / qdrant.dense / qdrant.sparse / rrf.merge / rerank.cross_encoder,每段含 input/output/elapsed_ms。
- `rag/app/main.py` — /query 包 'rag.query' trace + rewrite/critique 子 span,透传给 retriever.search;/health.capabilities 新增 langfuse_enabled & langfuse_host;startup 触发 lazy init。
- `rag/app/api/ingest.py` — /ingest 包 'rag.ingest' trace + pick_chunker / chunk.run / retriever.add 三段 span。
- `rag/app/api/retrieve.py` — /retrieve 包 'rag.retrieve_api' trace + 透传给 retriever.search 避免双 trace。
- `rag/requirements.txt` — 加入 langfuse==2.50.0 (~3MB,无 ML 依赖)。
- `deploy/docker-compose.yml` — rag 服务透传 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST。
- `deploy/.env.example` — Langfuse 配置占位 + cloud/自托管注册指引。

### 影响范围
- ✅ 不配 keys: 行为完全不变,启动多 1 条 INFO 日志。
- ✅ 配 keys: Langfuse UI 可视化每一次 /query / /ingest / /retrieve 的完整 trace 树。Trace 树示例:
  ```
  rag.query (root)
  ├── rewrite
  ├── rag.retrieve (透传子 trace)
  │   ├── bm25.search [hits=30]
  │   ├── bge.encode_query [dense_dim=1024, sparse_terms=15]
  │   ├── qdrant.dense [hits=30]
  │   ├── qdrant.sparse [hits=30]
  │   ├── rrf.merge [fused=30]
  │   └── rerank.cross_encoder [reranked=5]
  └── critique
  ```
- ✅ /health.capabilities 新增 langfuse_enabled & langfuse_host 两字段,前端/CLI 可探测。
- ✅ search() 新增可选 parent_trace 参数 (默认 None),向后兼容。
- ➖ 启动时间 +0.3s (轻度,主要是 langfuse 包 import)。
- ➖ 单次请求 overhead < 2ms (异步 flush)。
- ➖ 镜像 +3MB (langfuse 包)。

### 验证方式
```bash
# 1. 不开 Langfuse (默认):
curl -s http://localhost:8001/health | jq '.capabilities.langfuse_enabled'
# 期望: false

# 2. 开 Langfuse:
# 注册 https://cloud.langfuse.com -> Settings -> API Keys
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
docker compose restart rag
curl -s http://localhost:8001/health | jq '.capabilities.langfuse_enabled'
# 期望: true

# 3. 跑一次 /query 看 trace:
curl -s -X POST http://localhost:8001/query -H 'Content-Type: application/json' \
  -d '{"question":"DATE_FORMAT 怎么改","top_k":3}' | jq '.chunks[].id'
# 然后 Langfuse UI -> Traces -> 找 'rag.query',点开看完整 6 段 span 树。
```

### 回滚
```bash
git revert <本 SHA>
```
回滚后 observability.py 被移除,所有 import 失败 -> rag 启动失败。如需仅关观测、保留代码,设 LANGFUSE_PUBLIC_KEY= LANGFUSE_SECRET_KEY= 即可。

---

## [v2-step-06] 2026-05-21 — Late Chunking + 语义分块

**对应提交**: `feat(rag): Late Chunking + semantic chunking`

### 动机
step 4-5 后 BGE-M3 与 Qdrant 三路检索已接上,但长文档仍是被当作一个整体入库。这在实际业务 (并不是 demo 6 条 cheat-sheet) 会让召回质量明显下降。Jina AI 2024 提出 Late Chunking: "先全文 encode 拿到 token-level embeddings,再按 chunk 范围做池化",让每个 chunk 的 embedding 仍然携全文上下文。本步同时提供语义分块作为默认。

### 设计要点
- **两策略**: `semantic` (默认,句子相似度动态合并) 与 `late` (全文 token 池化)。调用者可在 /ingest 请求中切换。
- **Late Chunking 实现**: 全文 `encode_full` 拿 colbert_vecs → 字符窗口切块 → char→token 近似映射 → 按范围平均。不依赖 offset_mapping,足够分项生产。
- **避免重复 encode**: chunker 产出的 chunk 可携 `embedding`,retriever.add() 检测到后跳过重新 encode 直接写 Qdrant。Late 路径 ≈1/N 的计算量。
- **语义分块低依赖**: BGE 不可用时退化为 hash 向量计算句间相似度,仍能带来一些变动性 (总比定长切好)。
- **句子切分**: 中英文混排正则,保留句末标点,过短碎片会被合到前句 (避免 "N。" 这种碎片)。
- **多级配置表达力**: semantic 合并阈值 0.62 / 上限 1200 字;late 窗口 600 字 / overlap 80 字。都可调。

---

## [v2-step-05] 2026-05-21 — Qdrant + 三路混合检索 + RRF

对应: `feat(rag): Qdrant vector store + true 3-way hybrid retrieval`. profile=ml 可选启 Qdrant、RRF k=60、三态可用性。

## [v2-step-04] 2026-05-21 — BGE-M3 + bge-reranker-v2-m3

## [v2-step-03] 2026-05-21 — 真 LLM 驱动迁移流水线

## [v2-step-02] 2026-05-21 — DeepSeek-V3.1 LLM 接入

## [v2-step-01] 2026-05-21 — 升级路线图基线

---
## v1 关键提交归档
`6fa440f5` v1 final · `e434028b` v-text fix · `96f4709b` web full · `f738149d` Jinja2 fix · `177e3566` pom+SQL · `aefbd4fc` CKG · `7907a90c` JWT+SSE · `ac79f9bc` compose+Dockerfiles
