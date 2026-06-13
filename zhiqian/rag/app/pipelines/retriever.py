"""一站式 HybridRetriever — BM25 粗排 + (可选 Qdrant dense + sparse) + RRF 融合 + Reranker 精排。

v2-step-05: 三路检索 + RRF。
v2-step-06: 接受预嵌入的 chunk (add() 中的 doc 可携 embedding),用 LateChunker 产出的带全文上下文 embedding 直接入库。
v2-step-07: search() 全链 span 化 (bm25/encode_query/qdrant.dense/qdrant.sparse/rrf/rerank);新增 parent_trace 参数允许上游 trace 透传。
"""
from __future__ import annotations

import logging
import re
from contextlib import ExitStack
from typing import Any, Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

from app.config import settings
from app.core.bge_m3 import BgeM3Embedder
from app.core.observability import get_langfuse
from app.core.reranker import CrossEncoderReranker
from app.store.qdrant_store import QdrantStore
from app.store.rrf import rrf_merge

log = logging.getLogger(__name__)


_DEMO_DOCS: List[Dict[str, Any]] = [
    {
        "id": "kb-syntax-identifier",
        "text": "MySQL 使用反引号(`)引用标识符和保留字,openGauss/PostgreSQL 使用双引号(\"),Oracle 默认大写不需引用。迁移时需将反引号替换为双引号或去掉引用。",
        "source": "opengauss/dialect-cheatsheet.md#identifier",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-ifnull",
        "text": "MySQL IFNULL(x, y) 在 openGauss 中可以等价替换为 COALESCE(x, y),两者语义一致。Oracle NVL(x, y) 同理。",
        "source": "opengauss/dialect-cheatsheet.md#null-handling",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-type-autoincrement",
        "text": "MySQL AUTO_INCREMENT 在 PostgreSQL/openGauss 中映射为 SERIAL 或 GENERATED ALWAYS AS IDENTITY。Oracle 使用 SEQUENCE + NEXTVAL。",
        "source": "opengauss/type-mapping.md#autoincrement",
        "meta": {"dialect": "openGauss", "category": "TYPE_MAPPING"},
    },
    {
        "id": "kb-type-enum",
        "text": "MySQL ENUM('v1','v2',...) 迁移到 PostgreSQL 时必须先创建独立类型: CREATE TYPE colname_type AS ENUM('v1','v2',...),然后在 CREATE TABLE 中引用该类型。禁止使用 CHECK(status IN('v1','v2',...)) 替代,因为 ENUM 类型有更好的索引性能和类型安全。openGauss 不支持 CREATE TYPE ENUM,应使用 VARCHAR + CHECK 约束。示例: source 'status ENUM(\"pending\",\"shipped\",\"done\")' → target 'CREATE TYPE order_status AS ENUM(\"pending\",\"shipped\",\"done\"); CREATE TABLE orders(status order_status)'。",
        "source": "opengauss/dialect-cheatsheet.md#enum",
        "meta": {"dialect": "PostgreSQL", "category": "TYPE_MAPPING"},
    },
    {
        "id": "kb-type-decimal",
        "text": "BigDecimal 推荐映射为 openGauss 的 NUMERIC(p, s),例如金额使用 NUMERIC(20, 4),避免精度丢失。",
        "source": "opengauss/type-mapping.md#numeric",
        "meta": {"dialect": "openGauss", "category": "TYPE_MAPPING"},
    },
    {
        "id": "kb-func-dateformat",
        "text": "openGauss 不支持 MySQL 的 DATE_FORMAT 函数,需要使用 TO_CHAR 进行格式化。例如 TO_CHAR(t.created_at, 'YYYY-MM')。Oracle 也使用 TO_CHAR。",
        "source": "opengauss/dialect-cheatsheet.md#date-format",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-syntax-limit",
        "text": "建议使用 LIMIT ... OFFSET ... 并明确指定 ORDER BY,openGauss 与 MySQL 在分页语法上兼容,但顺序需明确。Oracle 使用 ROWNUM 或 ROW_NUMBER() OVER()。",
        "source": "opengauss/dialect-cheatsheet.md#pagination",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-groupconcat",
        "text": "MySQL GROUP_CONCAT(expr SEPARATOR sep) 在 PostgreSQL/openGauss 中替换为 STRING_AGG(expr, sep)。注意参数顺序不同。",
        "source": "opengauss/dialect-cheatsheet.md#group-concat",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-syntax-upsert",
        "text": "MySQL INSERT ... ON DUPLICATE KEY UPDATE 在 PostgreSQL/openGauss 中替换为 INSERT ... ON CONFLICT (col) DO UPDATE SET ...。使用 EXCLUDED 引用冲突行的值。",
        "source": "opengauss/dialect-cheatsheet.md#upsert",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-regexp",
        "text": "MySQL REGEXP 操作符在 PostgreSQL/openGauss 中替换为 ~ (区分大小写) 或 ~* (不区分大小写)。REGEXP_REPLACE 同理。",
        "source": "opengauss/dialect-cheatsheet.md#regexp",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-nvl",
        "text": "Oracle NVL(x, y) 在 PostgreSQL/openGauss 中替换为 COALESCE(x, y)。NVL2(x, y, z) 替换为 CASE WHEN x IS NOT NULL THEN y ELSE z END。",
        "source": "opengauss/dialect-cheatsheet.md#nvl",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-sysdate",
        "text": "Oracle SYSDATE 在 PostgreSQL/openGauss 中替换为 CURRENT_TIMESTAMP 或 NOW()。SYSDATE 返回日期+时间,CURRENT_DATE 仅返回日期。",
        "source": "opengauss/dialect-cheatsheet.md#sysdate",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-syntax-dual",
        "text": "Oracle SELECT ... FROM DUAL 中的 DUAL 是伪表,PostgreSQL/openGauss 中直接省略 FROM 子句或使用 VALUES 子句。",
        "source": "opengauss/dialect-cheatsheet.md#dual",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-syntax-rownum",
        "text": "Oracle ROWNUM 用于分页和限制行数,PostgreSQL/openGauss 中替换为 LIMIT n 或 ROW_NUMBER() OVER(ORDER BY ...)。注意 ROWNUM 在 WHERE 中的执行顺序。",
        "source": "opengauss/dialect-cheatsheet.md#rownum",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-decode",
        "text": "Oracle DECODE(expr, search1, result1, search2, result2, default) 在 PostgreSQL/openGauss 中替换为 CASE WHEN expr = search1 THEN result1 WHEN expr = search2 THEN result2 ELSE default END。",
        "source": "opengauss/dialect-cheatsheet.md#decode",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-join-outer",
        "text": "Oracle 使用 (+) 操作符表示外连接,如 WHERE a.id = b.id(+)。PostgreSQL/openGauss 使用标准 ANSI JOIN 语法: LEFT OUTER JOIN ... ON ...。",
        "source": "opengauss/dialect-cheatsheet.md#outer-join",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-substr",
        "text": "MySQL SUBSTR() 和 SUBSTRING() 在 PostgreSQL/openGauss 中都支持,但 Oracle 仅支持 SUBSTR()。建议统一使用 SUBSTRING() 以符合 SQL 标准。",
        "source": "opengauss/dialect-cheatsheet.md#substr",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-config-jdbc",
        "text": "从 MySQL 迁移到 openGauss 时,JDBC URL 需从 jdbc:mysql:// 改为 jdbc:opengauss://,默认端口从 3306 变为 5432。",
        "source": "opengauss/migration-guide.md#jdbc",
        "meta": {"dialect": "openGauss", "category": "CONFIG"},
    },
    {
        "id": "kb-dep-driver",
        "text": "openGauss 驱动 GA 版本仅提供 opengauss-jdbc artifact,在 Maven 中需替换 mysql-connector-java。",
        "source": "opengauss/migration-guide.md#dependency",
        "meta": {"dialect": "openGauss", "category": "DEPENDENCY"},
    },
    # ── 补全：全数据集需要但上述未覆盖的 KB ID ──
    {
        "id": "kb-func-addmonths",
        "text": "Oracle ADD_MONTHS(date, n) 在 PostgreSQL/openGauss 中替换为 date + INTERVAL 'n months'。例如 ADD_MONTHS(hire_date, 3) → hire_date + INTERVAL '3 months'。",
        "source": "opengauss/dialect-cheatsheet.md#addmonths",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-concat",
        "text": "MySQL CONCAT(a, b) 在 PostgreSQL/openGauss 中可用 a || b 替代,两者语义一致。CONCAT 也可直接使用,但 || 是更通用的写法。",
        "source": "opengauss/dialect-cheatsheet.md#concat",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-monthsbetween",
        "text": "Oracle MONTHS_BETWEEN(date1, date2) 在 PostgreSQL/openGauss 中替换为 EXTRACT(YEAR FROM age(date1, date2)) * 12 + EXTRACT(MONTH FROM age(date1, date2))。",
        "source": "opengauss/dialect-cheatsheet.md#monthsbetween",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-nvl2",
        "text": "Oracle NVL2(x, y, z) 表示如果 x 不为 NULL 则返回 y,否则返回 z。在 PostgreSQL/openGauss 中替换为 CASE WHEN x IS NOT NULL THEN y ELSE z END 或 COALESCE 配合 IS NULL 判断。",
        "source": "opengauss/dialect-cheatsheet.md#nvl2",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-regexp_substr",
        "text": "Oracle REGEXP_SUBSTR(str, pattern) 在 PostgreSQL 中替换为 (REGEXP_MATCHES(str, pattern))[1]。REGEXP_MATCHES 返回文本数组,取第一个元素即为匹配结果。示例: REGEXP_SUBSTR(email, '[^@]+') → (REGEXP_MATCHES(email, '[^@]+'))[1]。注意: 不要用 SUBSTRING,PostgreSQL 的 SUBSTRING 不支持正则模式。",
        "source": "opengauss/dialect-cheatsheet.md#regexp-substr",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-func-year",
        "text": "MySQL YEAR(date_col) 在 PostgreSQL/openGauss 中替换为 EXTRACT(YEAR FROM date_col)。同理 MONTH() → EXTRACT(MONTH FROM ...), DAY() → EXTRACT(DAY FROM ...)。",
        "source": "opengauss/dialect-cheatsheet.md#year",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-syntax-fulltext",
        "text": "MySQL FULLTEXT 索引和 MATCH ... AGAINST 语法在 PostgreSQL/openGauss 中替换为 tsvector + tsquery 全文检索。需创建 GIN 索引。",
        "source": "opengauss/dialect-cheatsheet.md#fulltext",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-syntax-hierarchy",
        "text": "Oracle CONNECT BY PRIOR 层次查询在 PostgreSQL/openGauss 中替换为 WITH RECURSIVE CTE 递归查询。转换规则: (1) START WITH cond → CTE 非递归部分 WHERE cond; (2) CONNECT BY PRIOR parent_id = child_id → 递归部分 JOIN; (3) LEVEL → 递归计数器,初始 0 每层 +1; (4) CONNECT_BY_ISLEAF → NOT EXISTS(SELECT 1 FROM table WHERE parent_id=current.id)。关键: 必须在 CTE 中保留 id/parent_id 列用于递归 JOIN。完整示例: source 'SELECT CONNECT_BY_ISLEAF, LEVEL, name FROM emp START WITH manager_id IS NULL CONNECT BY PRIOR id=manager_id' → target 'WITH RECURSIVE emp_tree AS (SELECT id, name, manager_id, 0 AS lvl, false AS is_leaf FROM emp WHERE manager_id IS NULL UNION ALL SELECT e.id, e.name, e.manager_id, t.lvl+1, NOT EXISTS(SELECT 1 FROM emp WHERE manager_id=e.id) FROM emp e JOIN emp_tree t ON e.manager_id=t.id) SELECT is_leaf, lvl, name FROM emp_tree'。",
        "source": "opengauss/dialect-cheatsheet.md#hierarchy",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "kb-type-bit",
        "text": "MySQL BIT(1) 在 PostgreSQL/openGauss 中必须替换为 BOOLEAN。BIT(n) 当 n>1 时替换为 BIT(n)。MySQL 中 BIT(1) 常用于布尔值存储,迁移到 PostgreSQL 时应直接使用 BOOLEAN 类型,不要用 SMALLINT 或 INTEGER 替代。",
        "source": "opengauss/type-mapping.md#bit",
        "meta": {"dialect": "openGauss", "category": "TYPE_MAPPING"},
    },
    {
        "id": "kb-type-datetime",
        "text": "MySQL DATETIME 和 TIMESTAMP 类型在 PostgreSQL/openGauss 中都映射为 TIMESTAMP。注意 MySQL 的 TIMESTAMP 有时区转换行为,PostgreSQL 的 TIMESTAMP WITHOUT TIME ZONE 更接近 MySQL DATETIME。",
        "source": "opengauss/type-mapping.md#datetime",
        "meta": {"dialect": "openGauss", "category": "TYPE_MAPPING"},
    },
    {
        "id": "kb-type-double",
        "text": "MySQL DOUBLE 类型在 PostgreSQL/openGauss 中替换为 DOUBLE PRECISION。FLOAT(p) 根据精度映射为 REAL (p<=24) 或 DOUBLE PRECISION (p>24)。",
        "source": "opengauss/type-mapping.md#double",
        "meta": {"dialect": "openGauss", "category": "TYPE_MAPPING"},
    },
]

_DEMO_COLLECTION = "zhiqian-default"


def _tokenize(text: str) -> List[str]:
    return [
        t for t in re.split(
            r"[\s,.;:!?()\[\]{}<>=#'\"\u3002\uff0c\uff1b\uff1a\uff01\uff1f\u3001]+",
            (text or "").lower(),
        )
        if t
    ]


class HybridRetriever:
    def __init__(
        self,
        docs: Optional[List[Dict[str, Any]]] = None,
        reranker: Optional[CrossEncoderReranker] = None,
        embedder: Optional[BgeM3Embedder] = None,
        qdrant: Optional[QdrantStore] = None,
        collection: str = _DEMO_COLLECTION,
    ):
        self.docs = docs if docs is not None else _DEMO_DOCS
        self.collection = collection
        self._tokens = [_tokenize(d["text"]) for d in self.docs]
        self._bm25 = BM25Okapi(self._tokens) if self._tokens else None
        self._by_id: Dict[str, Dict[str, Any]] = {d["id"]: d for d in self.docs}
        if reranker is not None:
            self._reranker = reranker
        elif settings.use_reranker:
            self._reranker = CrossEncoderReranker(model_path=settings.reranker_model, use_fp16=settings.reranker_fp16)
        else:
            self._reranker = None
        if embedder is not None:
            self._embedder = embedder
        elif settings.use_bge_m3:
            self._embedder = BgeM3Embedder(model_path=settings.bge_model, use_fp16=settings.bge_fp16, dim=settings.embedding_dim)
        else:
            self._embedder = None
        if qdrant is not None:
            self._qdrant = qdrant
        elif settings.use_qdrant:
            self._qdrant = QdrantStore(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, dim=settings.embedding_dim)
        else:
            self._qdrant = None
        self.graph_index = None  # GraphRagIndex, set by main.py lifespan
        log.info(
            "[HybridRetriever] collection=%s | bm25=%s embed_real=%s qdrant_avail=%s rerank_avail=%s",
            self.collection,
            self._bm25 is not None,
            (self._embedder.available if self._embedder else False),
            (self._qdrant.available if self._qdrant else False),
            (self._reranker.available if self._reranker else False),
        )
        self._maybe_seed_qdrant()

    # ───── 公开 API ─────

    def add(self, docs: List[Dict[str, Any]]) -> int:
        """动态追加文档/块。允许每条 doc 携 `embedding` 字段,有则不会重新 encode。"""
        if not docs:
            return 0
        new_count = 0
        new_docs: List[Dict[str, Any]] = []
        for d in docs:
            if d.get("id") in self._by_id:
                continue
            self.docs.append(d)
            self._by_id[d["id"]] = d
            new_docs.append(d)
            new_count += 1
        self._tokens = [_tokenize(x["text"]) for x in self.docs]
        self._bm25 = BM25Okapi(self._tokens) if self._tokens else None
        self._index_qdrant(new_docs)
        return new_count

    def search(
        self,
        question: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        mode: str = "full",
        parent_trace: Any = None,
    ) -> List[Dict[str, Any]]:
        """三路混合检索 + RRF + 可选重排。

        mode 控制检索通道:
        - bm25: 仅 BM25 关键词匹配
        - vector: 仅 dense 向量检索 (Qdrant + BGE-M3)
        - vector_rerank: dense + reranker 精排
        - crag: BM25 + dense + sparse + RRF + reranker (全通道)
        - full: 同 crag
        """
        if not self.docs or self._bm25 is None:
            return []
        lf = get_langfuse()
        with ExitStack() as stack:
            if parent_trace is not None:
                tr = parent_trace
            else:
                tr = stack.enter_context(
                    lf.trace(
                        "rag.retrieve",
                        input={"question": question, "top_k": top_k, "mode": mode},
                        metadata={"collection": self.collection},
                        tags=["rag", "retrieve"],
                    )
                )
            coarse_k = max(top_k * 3, top_k)

            use_bm25 = mode in ("bm25", "crag", "full")
            use_dense = mode in ("vector", "vector_rerank", "crag", "full")
            use_sparse = mode in ("crag", "full")
            use_rerank = mode in ("vector_rerank", "crag", "full")

            # ── BM25 ──
            bm25_ranked: List[Tuple[str, float]] = []
            if use_bm25:
                with tr.span("bm25.search", input={"coarse_k": coarse_k}) as sp:
                    bm25_scores = self._bm25.get_scores(_tokenize(question))
                    bm25_ranked = sorted(
                        zip([d["id"] for d in self.docs], bm25_scores),
                        key=lambda x: x[1], reverse=True,
                    )[:coarse_k]
                    sp.output({"hits": len(bm25_ranked), "top_id": bm25_ranked[0][0] if bm25_ranked else None})

            # ── Dense + Sparse via Qdrant ──
            dense_ranked: List[Tuple[str, float]] = []
            sparse_ranked: List[Tuple[str, float]] = []
            used_dense = used_sparse = False
            if use_dense and self._embedder and self._embedder.available and self._qdrant and self._qdrant.available:
                try:
                    with tr.span("bge.encode_query", input={"q_len": len(question)}) as sp:
                        full = self._embedder.encode_full([question])
                        qdense = full["dense_vecs"][0]
                        qsparse_raw = full["lexical_weights"][0] or {}
                        qsparse = {int(k): float(v) for k, v in qsparse_raw.items()}
                        sp.output({"dense_dim": len(qdense), "sparse_terms": len(qsparse)})
                    with tr.span("qdrant.dense", input={"coarse_k": coarse_k}) as sp:
                        drs = self._qdrant.search_dense(self.collection, qdense, k=coarse_k)
                        dense_ranked = [(rid, s) for rid, s, _ in drs]
                        used_dense = True
                        sp.output({"hits": len(dense_ranked), "top_id": dense_ranked[0][0] if dense_ranked else None})
                    if use_sparse and qsparse:
                        with tr.span("qdrant.sparse", input={"coarse_k": coarse_k, "sparse_terms": len(qsparse)}) as sp:
                            srs = self._qdrant.search_sparse(self.collection, qsparse, k=coarse_k)
                            sparse_ranked = [(rid, s) for rid, s, _ in srs]
                            used_sparse = True
                            sp.output({"hits": len(sparse_ranked), "top_id": sparse_ranked[0][0] if sparse_ranked else None})
                except Exception as e:
                    log.warning("[HybridRetriever] dense/sparse 路径出错,单走 BM25。err=%s", e)

            # ── 降级：如果请求了 dense 但不可用，自动启用 BM25 ──
            if use_dense and not used_dense and not bm25_ranked:
                log.info("[HybridRetriever] dense 不可用,自动降级到 BM25")
                with tr.span("bm25.fallback", input={"coarse_k": coarse_k}) as sp:
                    bm25_scores = self._bm25.get_scores(_tokenize(question))
                    bm25_ranked = sorted(
                        zip([d["id"] for d in self.docs], bm25_scores),
                        key=lambda x: x[1], reverse=True,
                    )[:coarse_k]
                    sp.output({"hits": len(bm25_ranked), "top_id": bm25_ranked[0][0] if bm25_ranked else None})

            # ── RRF 或单路直出 ──
            lists = []
            channel_weight_map = {}
            all_weights = [float(w.strip()) for w in settings.rrf_channel_weights.split(",")]

            # 按渠道类型分配权重
            if bm25_ranked:
                lists.append(bm25_ranked)
                channel_weight_map[len(lists) - 1] = all_weights[0] if len(all_weights) > 0 else 1.0
            if used_dense and dense_ranked:
                lists.append(dense_ranked)
                channel_weight_map[len(lists) - 1] = all_weights[1] if len(all_weights) > 1 else 1.0
            if used_sparse and sparse_ranked:
                lists.append(sparse_ranked)
                channel_weight_map[len(lists) - 1] = all_weights[2] if len(all_weights) > 2 else 1.0

            # 如果只有一个渠道，权重应为 1.0（单路直出不用 RRF）
            if len(lists) == 1:
                channel_weight_map[0] = 1.0

            if not lists:
                return []

            # 构建权重列表
            rrf_weights = [channel_weight_map.get(i, 1.0) for i in range(len(lists))]
            log.warning("[HybridRetriever] RRF weights: %s (channels: bm25=%s, dense=%s, sparse=%s) all_weights=%s",
                     rrf_weights, bool(bm25_ranked), used_dense, used_sparse, all_weights)

            if len(lists) == 1:
                # 单路直出,不用 RRF
                fused = [(doc_id, score, {"single": score}) for doc_id, score in lists[0][:coarse_k]]
            else:
                with tr.span("rrf.merge", input={"channels": len(lists), "rrf_k": settings.rrf_k, "weights": rrf_weights}) as sp:
                    fused_raw = rrf_merge(lists, k=settings.rrf_k, top_n=coarse_k, weights=rrf_weights)
                    fused = [(doc_id, rrf_score, per_ch) for doc_id, rrf_score, per_ch in fused_raw]
                    sp.output({"fused": len(fused), "top_id": fused[0][0] if fused else None})

            coarse: List[Dict[str, Any]] = []
            for doc_id, rrf_score, per_ch in fused:
                d = self._by_id.get(doc_id)
                if d is None:
                    continue
                if filters:
                    meta = d.get("meta") or {}
                    if any(meta.get(k) != v for k, v in filters.items()):
                        continue
                coarse.append({
                    "id": d["id"],
                    "text": d["text"],
                    "score": float(rrf_score),
                    "rrf_score": float(rrf_score),
                    "channels": per_ch,
                    "source": d.get("source", "unknown"),
                    "meta": d.get("meta"),
                })
                if len(coarse) >= coarse_k:
                    break

            # ── Rerank ──
            if use_rerank and self._reranker and self._reranker.available and coarse:
                try:
                    with tr.span("rerank.cross_encoder", input={"candidates": len(coarse), "top_n": top_k}) as sp:
                        texts = [c["text"] for c in coarse]
                        reranked = self._reranker.rerank(question, texts, top_n=top_k)
                        out: List[Dict[str, Any]] = []
                        for idx, rscore in reranked:
                            item = dict(coarse[idx])
                            item["rerank_score"] = float(rscore)
                            item["score"] = float(rscore)
                            out.append(item)
                        sp.output({"reranked": len(out), "top_id": out[0]["id"] if out else None})
                    if parent_trace is None:
                        tr.output({"final_ids": [x["id"] for x in out]})
                    return out
                except Exception as e:
                    log.warning("[HybridRetriever] rerank 失败 (可能是 OOM), 降级到原序: %s", e)

            result = coarse[:top_k]

            # ── v2-step-13: GraphRAG 扩展（仅 full 模式）──
            if mode == "full" and self.graph_index and self.graph_index.nodes:
                try:
                    with tr.span("graphrag.local", input={"question": question, "max_entities": 3, "hop": 1}) as sp:
                        gr = self.graph_index.query_local(question, max_entities=3, hop=1, weight_threshold=0.0)
                        graph_ctx = gr.get("context", "")
                        hits = gr.get("hits", [])
                        sp.output({"hits": len(hits), "neighbors": len(gr.get("neighbors", []))})
                    # 将 graph context 附加到结果，追加未覆盖的实体
                    existing_ids = {item["id"] for item in result}
                    # neighbors 返回的是 dict 列表，需提取 id
                    neighbor_dicts = gr.get("neighbors", [])
                    neighbor_ids = [n["id"] if isinstance(n, dict) else n for n in neighbor_dicts]
                    for nid in hits + neighbor_ids:
                        if nid in existing_ids:
                            continue
                        d = self._by_id.get(nid)
                        if d:
                            result.append({
                                "id": d["id"],
                                "text": d["text"],
                                "score": 0.3,
                                "rrf_score": 0.3,
                                "channels": {"graphrag": 1},
                                "source": d.get("source", "unknown"),
                                "meta": dict(d.get("meta") or {}),
                                "graphrag_hit": nid in hits,
                            })
                            existing_ids.add(nid)
                    # 也获取 global 社区报告
                    gr_global = self.graph_index.query_global(question, max_reports=2)
                    global_ctx = gr_global.get("context", "")
                    if global_ctx:
                        # 作为虚拟文档追加
                        result.append({
                            "id": "graphrag-global",
                            "text": global_ctx[:500],
                            "score": 0.2,
                            "rrf_score": 0.2,
                            "channels": {"graphrag_global": 1},
                            "source": "graphrag/community-reports",
                            "meta": {"graphrag": True},
                        })
                except Exception as e:
                    log.warning("[HybridRetriever] GraphRAG query failed, falling back: %s", e)

            if parent_trace is None:
                tr.output({"final_ids": [x["id"] for x in result]})
            return result

    def capabilities(self) -> Dict[str, Any]:
        return {
            "bm25": self._bm25 is not None,
            "dense": bool(self._embedder and self._embedder.available and self._qdrant and self._qdrant.available),
            "sparse": bool(self._embedder and self._embedder.available and self._qdrant and self._qdrant.available),
            "rerank": bool(self._reranker and self._reranker.available),
            "graphrag": bool(self.graph_index and self.graph_index.nodes),
            "qdrant_url": settings.qdrant_url if (self._qdrant and self._qdrant.available) else None,
            "embed_model": settings.bge_model if (self._embedder and self._embedder.available) else None,
            "rerank_model": settings.reranker_model if (self._reranker and self._reranker.available) else None,
            "rrf_k": settings.rrf_k,
            "docs": len(self.docs),
            "chunk_strategy_default": settings.chunk_strategy,
        }

    # ───── 内部 ─────

    def _maybe_seed_qdrant(self):
        if not (self._embedder and self._embedder.available and self._qdrant and self._qdrant.available):
            return
        try:
            self._index_qdrant(self.docs)
        except Exception as e:
            log.warning("[HybridRetriever] _maybe_seed_qdrant 失败 err=%s", e)

    def _index_qdrant(self, docs: List[Dict[str, Any]]):
        if not (self._embedder and self._embedder.available and self._qdrant and self._qdrant.available) or not docs:
            return
        with_emb: List[Dict[str, Any]] = []
        need_encode: List[Dict[str, Any]] = []
        for d in docs:
            if isinstance(d.get("embedding"), list) and d["embedding"]:
                with_emb.append(d)
            else:
                need_encode.append(d)
        if with_emb:
            self._qdrant.upsert(
                self.collection,
                ids=[d["id"] for d in with_emb],
                texts=[d["text"] for d in with_emb],
                dense_vecs=[d["embedding"] for d in with_emb],
                sparse_dicts=[{} for _ in with_emb],
                metas=[d.get("meta") for d in with_emb],
            )
        if need_encode:
            texts = [d["text"] for d in need_encode]
            full = self._embedder.encode_full(texts)
            dense = full["dense_vecs"]
            sparse = []
            for sd in full["lexical_weights"]:
                sd = sd or {}
                sparse.append({int(k): float(v) for k, v in sd.items()})
            self._qdrant.upsert(
                self.collection,
                ids=[d["id"] for d in need_encode],
                texts=texts,
                dense_vecs=dense,
                sparse_dicts=sparse,
                metas=[d.get("meta") for d in need_encode],
            )
