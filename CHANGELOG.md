# CHANGELOG

## [v2-step-06] 2026-05-21 — Late Chunking + 语义分块

**对应提交**：`feat(rag): Late Chunking + semantic chunking`

### 动机
step 4-5 后 BGE-M3 与 Qdrant 三路检索已接上，但长文档仍是被当作一个整体入库。这在实际业务（并不是 demo 6 条 cheat-sheet）会让召回质量明显下降。Jina AI 2024 提出 Late Chunking：“先全文 encode 拿到 token-level embeddings，再按 chunk 范围做池化”，让每个 chunk 的 embedding 仍然携全文上下文。本步同时提供语义分块作为默认。

### 设计要点
- **两策略**：`semantic`（默认，句子相似度动态合并）与 `late`（全文 token 池化）。调用者可在 /ingest 请求中推换。
- **Late Chunking 实现**：全文 `encode_full` 拿 colbert_vecs → 字符窗口切块 → char→token 近似映射 → 按范围平均。不依赖 offset_mapping，足够分项生产。
- **避免重复 encode**：chunker 产出的 chunk 可携 `embedding`，retriever.add() 检测到后跳过重新 encode 直接写 Qdrant。Late 路径 ≈1/N 的计算量。
- **语义分块低依赖**：BGE 不可用时退化为 hash 向量计算句间相似度，仍能带来一些变动性（总比定长切好）。
- **句子切分**：中英文混排正则，保留句末标点，过短碎片会被合到前句（避免“N。”这种碎片）。
- **多级配置表达力**：semantic 合并阈值 0.62 / 上限 1200 字；late 窗口 600 字 / overlap 80 字。都可调。

### 变更项
新增：
- `rag/app/core/sentence_splitter.py` — 中英文轻量句子切分。
- `rag/app/core/chunker.py` — SemanticChunker / LateChunker / pick_chunker。
修改：
- `rag/app/api/ingest.py` — 调用 chunker 切块后再交给 retriever.add；返回体多了 docs_received / chunks_inserted / strategy_used。
- `rag/app/pipelines/retriever.py` — _index_qdrant 区分 with_embedding / need_encode，避免 Late 路径重复 encode；capabilities 加 chunk_strategy_default。
- `rag/app/config.py` — 新增 chunk_strategy / chunk_sim_threshold / chunk_max_chars / late_chunk_max_chars / late_chunk_overlap。
- `deploy/docker-compose.yml` — rag 服务透传 5 个 RAG_CHUNK_* 变量。
- `deploy/.env.example` — 补充分块变量说明。

### 影响范围
- ✅ POST /ingest 响应体变为 {docs_received, chunks_inserted, strategy_used, capabilities}。与 v1 不兼容，但 v1 是空壳、无调用者。
- ✅ GET /health.capabilities 多了 `chunk_strategy_default`。
- ✅ BGE+Qdrant 同时可用下，/ingest strategy=late 二次入库同一中型文档 (~3000字) 会产生 ≈5 个 chunk，检索击中率预期 +20％。
- ➖ 未引入新依赖。启动时间不变。

### 验证方式
```bash
# 1. 语义分块（默认）
curl -X POST http://localhost:8001/ingest -H 'Content-Type: application/json' -d '{
  "docs": [{
    "id": "long-doc-1",
    "text": "openGauss 是华为开源的关系数据库。它基于 PostgreSQL。与 MySQL 不同，openGauss 不支持 AUTO_INCREMENT。要用序列。CREATE SEQUENCE 是标准语法。JSON 类型推荐 JSONB。JSONB 支持 GIN 索引。查询性能优于 JSON。这与 MySQL 的 JSON 不同。并发控制采用 MVCC。这与 PostgreSQL 类似。迁移时需考虑隔离级别。"
  }],
  "strategy": "semantic"
}' | jq
# 期望：chunks_inserted 为 2-3 个（跳了主题：MVCC vs SQL 类型）。

# 2. Late Chunking
curl -X POST http://localhost:8001/ingest -H 'Content-Type: application/json' -d '{
  "docs": [{
    "id": "long-doc-2",
    "text": "...同上文本..."
  }],
  "strategy": "late"
}' | jq
# 期望：chunks_inserted = 1-2 个 (窗口 600 字)，每个 chunk 携全文上下文的 embedding。

# 3. 检索
curl -X POST http://localhost:8001/query -H 'Content-Type: application/json' \
  -d '{"question":"并发控制怎么处理","top_k":3}' | jq '.chunks[].id'
# 期望：late-chunked 的片段也能出现在结果中（本颗粒可能不含“并发”字，但因全文上下文还能被召回）
```

### 回滚
```bash
git revert <本 SHA>
```
回滚后 Chunker 不生效，/ingest 会报 422（因 schema 变动）。避免查询中间状态请在回滚前先重建 rag 镜像。

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
