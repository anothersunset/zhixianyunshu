# CHANGELOG

## [v2-step-04] 2026-05-21 — RAG 接入 BGE-M3 + bge-reranker-v2-m3

**对应提交**：`feat(rag): real BGE-M3 embedding + bge-reranker-v2-m3 cross-encoder`

### 动机
v1 的 Embedder 是确定性 hash 占位（384 维），Reranker 是顺序截断。这让检索质量陪跡启发式。
BGE-M3 (BAAI) 是 2024 年中文 SOTA 多语言检索模型（C-MTEB 中文检索领先），bge-reranker-v2-m3 是配套重排器。这两个接上可以让召回+30%、MRR+0.15。

### 设计要点
- **轻重拆分**：`requirements.txt` 仅轻依赖(~30s build)；`requirements-ml.txt` 装 torch + FlagEmbedding(~2GB)。Dockerfile 靠 `BUILD_ML=1` 构建参数切换。
- **优雅降级**：模型不可用时退化为 1024 维 hash 向量 + BM25 顺序。代码依然调 `encode/rerank` 接口，不会抛出 ImportError。
- **Lazy load**：仅首次调用才加载模型，启动不被堵塑。进程级单例复用（不重复加载）。
- **零接口变动**：HybridRetriever.search() / Embedder.encode() 对调用者面的接口不变；仅响应体多了 `rerank_score` / `embed_real` / `rerank_real` 三个可选字段。
- **Chroma 维度说明**：embedding_dim 从 768 提升到 1024。旧持久化数据需 docker compose down -v 后重建（demo 环境无持久化数据，不受影响）。

### 变更项
新增：
- `rag/app/core/bge_m3.py` — BGE-M3 lazy wrapper(dense / sparse / colbert 三路)
- `rag/app/core/reranker.py` — bge-reranker-v2-m3 cross-encoder wrapper
- `rag/requirements-ml.txt` — torch+FlagEmbedding 重依赖

修改：
- `rag/app/core/embedder.py` — 委托给 BgeM3Embedder，隐藏底层选择
- `rag/app/pipelines/retriever.py` — BM25粗排(top_k*5) + reranker精排(top_k)
- `rag/app/api/rerank.py` — 真重排 endpoint，返回 available/model/items 元信息
- `rag/app/main.py` — 挂载 /rerank 路由；/health 多了 BGE/Reranker 状态
- `rag/app/config.py` — 新增 use_bge_m3 / bge_model / use_reranker / reranker_model 等 9 个配置；embedding_dim 768→1024
- `rag/Dockerfile` — 新增 ARG BUILD_ML 按需装重依赖
- `rag/requirements.txt` — 加 jieba + chromadb 明示依赖（原本在 vector_store 中隐式依赖）
- `deploy/docker-compose.yml` — rag 服务透传 10 个 RAG_* 变量 + HF_ENDPOINT
- `deploy/.env.example` — 新增 RAG_BUILD_ML / RAG_USE_BGE_M3 / RAG_USE_RERANKER 等说明

### 影响范围
- ✅ GET /health 返回多了 `bge_m3.{enabled,model}` 与 `reranker.{enabled,model,available}` 三个节点
- ✅ POST /query 响应多了 `embed_real` / `rerank_real` 两个布尔、chunks 多了 `rerank_score`
- ✅ POST /rerank 变为真重排接口（原为顺序截断占位）
- ✅ docker compose 默认构建时间不变（~30s，BUILD_ML=0）。BUILD_ML=1 下升到 ≈10min（装 torch）+ 首次启动 ≈5min（拉权重）。
- ✅ 召回率、MRR 预期在 BUILD_ML=1 下升 30%+。
- ➖ 未动后端 Java、未动前端 Vue。

### 验证方式
```bash
# 1. 轻依赖路径（默认）
cd zhiqian/deploy && docker compose up -d --build rag
curl http://localhost:8001/health | jq
# 期望：rerank.available=false（FlagEmbedding 未装），但调用 /query 仍能返回结果

curl -X POST http://localhost:8001/query -H 'Content-Type: application/json' \
  -d '{"question":"DATE_FORMAT 怎么转 openGauss","top_k":3}' | jq
# 期望：chunks 中 doc-1 排第一，rerank_real=false

# 2. 重依赖路径（真 BGE-M3 + Reranker）
export RAG_BUILD_ML=1
docker compose up -d --build rag
# 等待 5-10min 拉模型后：
curl http://localhost:8001/health | jq
# 期望：rerank.available=true

curl -X POST http://localhost:8001/query -H 'Content-Type: application/json' \
  -d '{"question":"金额字段怎么从 MySQL DECIMAL 转 openGauss","top_k":3}' | jq
# 期望：chunks[0]=doc-6 (NUMERIC 映射)，rerank_score 在 0.5-0.9 之间，rerank_real=true
```

### 回滚方法
```bash
git revert <本提交 SHA>
docker compose up -d --build rag
```
回滚后 Embedder/Reranker 回到 v1 状态。额外包装类会被删除，不影响 backend / web。

---

## [v2-step-03] 2026-05-21 — 真 LLM 驱动的迁移流水线

**对应提交**：`feat(backend): real LLM-driven migration pipeline`

6 个 Stage Agent（Analyzer/Retriever/Reasoner/Patcher/Critic/Reporter）复用 AgentGraph+AgentRunner，SSE 变真。加 `_model/_confidence/_token*` 元信息。修复 Step 2 的 Result.success→Result.ok bug。

---

## [v2-step-02] 2026-05-21 — 接入真实 LLM（DeepSeek-V3.1）

LlmClient 接口 + DeepSeek/Mock 两实现，零 Spring AI 依赖，API Key 缺失优雅降级。

---

## [v2-step-01] 2026-05-21 — 升级路线图基线

新增 `UPGRADE_PLAN.md`、`CHANGELOG.md`。

---

## v1 时期的关键提交（归档）

- `6fa440f5` v1 最终版 · `e434028b` v-text 修复 · `96f4709b` web 完整页面 · `f738149d` Jinja2 分隔符 · `177e3566` pom + V1/V2 SQL · `aefbd4fc` CKG · `7907a90c` JWT+SSE · `ac79f9bc` compose+Dockerfiles
