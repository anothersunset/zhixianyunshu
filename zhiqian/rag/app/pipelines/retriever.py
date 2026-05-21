"""一站式 HybridRetriever — BM25 粗排 + (可选 Qdrant dense + sparse) + RRF 融合 + Reranker 精排。

v2-step-05：三路检索 + RRF。
v2-step-06：接受预嵌入的 chunk（add() 中中的 doc 可携 embedding），用 LateChunker 产出的带全文上下文 embedding 直接入库。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

from app.config import settings
from app.core.bge_m3 import BgeM3Embedder
from app.core.reranker import CrossEncoderReranker
from app.store.qdrant_store import QdrantStore
from app.store.rrf import rrf_merge

log = logging.getLogger(__name__)


_DEMO_DOCS: List[Dict[str, Any]] = [
    {
        "id": "doc-1",
        "text": "openGauss 不支持 MySQL 的 DATE_FORMAT 函数，需要使用 TO_CHAR 进行格式化。例如 TO_CHAR(t.created_at, 'YYYY-MM')。",
        "source": "opengauss/dialect-cheatsheet.md#date-format",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "doc-2",
        "text": "MySQL IFNULL(x, y) 在 openGauss 中可以等价替换为 COALESCE(x, y)，两者语义一致。",
        "source": "opengauss/dialect-cheatsheet.md#null-handling",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "doc-3",
        "text": "从 MySQL 迁移到 openGauss 时，JDBC URL 需从 jdbc:mysql:// 改为 jdbc:opengauss://，默认端口从 3306 变为 5432。",
        "source": "opengauss/migration-guide.md#jdbc",
        "meta": {"dialect": "openGauss", "category": "CONFIG"},
    },
    {
        "id": "doc-4",
        "text": "openGauss 驱动 GA 版本仅提供 opengauss-jdbc artifact，在 Maven 中需替换 mysql-connector-java。",
        "source": "opengauss/migration-guide.md#dependency",
        "meta": {"dialect": "openGauss", "category": "DEPENDENCY"},
    },
    {
        "id": "doc-5",
        "text": "建议使用 LIMIT ... OFFSET ... 并明确指定 ORDER BY，openGauss 与 MySQL 在分页语法上兼容，但顺序需明确。",
        "source": "opengauss/dialect-cheatsheet.md#pagination",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "doc-6",
        "text": "BigDecimal 推荐映射为 openGauss 的 NUMERIC(p, s)，例如金额使用 NUMERIC(20, 4)，避免精度丢失。",
        "source": "opengauss/type-mapping.md#numeric",
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
        """动态追加文档／块。允许每条 doc 携 `embedding` 字段，有则不会重新 encode。"""
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
    ) -> List[Dict[str, Any]]:
        if not self.docs or self._bm25 is None:
            return []
        coarse_k = max(top_k * 5, top_k)
        bm25_scores = self._bm25.get_scores(_tokenize(question))
        bm25_ranked = sorted(
            zip([d["id"] for d in self.docs], bm25_scores),
            key=lambda x: x[1], reverse=True,
        )[:coarse_k]
        dense_ranked: List[Tuple[str, float]] = []
        sparse_ranked: List[Tuple[str, float]] = []
        used_dense = used_sparse = False
        if self._embedder and self._embedder.available and self._qdrant and self._qdrant.available:
            try:
                full = self._embedder.encode_full([question])
                qdense = full["dense_vecs"][0]
                qsparse_raw = full["lexical_weights"][0] or {}
                qsparse = {int(k): float(v) for k, v in qsparse_raw.items()}
                drs = self._qdrant.search_dense(self.collection, qdense, k=coarse_k)
                dense_ranked = [(rid, s) for rid, s, _ in drs]
                used_dense = True
                if qsparse:
                    srs = self._qdrant.search_sparse(self.collection, qsparse, k=coarse_k)
                    sparse_ranked = [(rid, s) for rid, s, _ in srs]
                    used_sparse = True
            except Exception as e:
                log.warning("[HybridRetriever] dense/sparse 路径出错，单走 BM25。err=%s", e)
        lists = [bm25_ranked]
        if used_dense and dense_ranked:
            lists.append(dense_ranked)
        if used_sparse and sparse_ranked:
            lists.append(sparse_ranked)
        fused = rrf_merge(lists, k=settings.rrf_k, top_n=coarse_k)
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
        if self._reranker and self._reranker.available and coarse:
            texts = [c["text"] for c in coarse]
            reranked = self._reranker.rerank(question, texts, top_n=top_k)
            out: List[Dict[str, Any]] = []
            for idx, rscore in reranked:
                item = dict(coarse[idx])
                item["rerank_score"] = float(rscore)
                item["score"] = float(rscore)
                out.append(item)
            return out
        return coarse[:top_k]

    def capabilities(self) -> Dict[str, Any]:
        return {
            "bm25": self._bm25 is not None,
            "dense": bool(self._embedder and self._embedder.available and self._qdrant and self._qdrant.available),
            "sparse": bool(self._embedder and self._embedder.available and self._qdrant and self._qdrant.available),
            "rerank": bool(self._reranker and self._reranker.available),
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
        # 区分：携 embedding 的直接写；不携的重新 encode_full
        with_emb: List[Dict[str, Any]] = []
        need_encode: List[Dict[str, Any]] = []
        for d in docs:
            if isinstance(d.get("embedding"), list) and d["embedding"]:
                with_emb.append(d)
            else:
                need_encode.append(d)
        # 写预嵌入部分（late-chunked）：sparse 为空，dense 直接走
        if with_emb:
            self._qdrant.upsert(
                self.collection,
                ids=[d["id"] for d in with_emb],
                texts=[d["text"] for d in with_emb],
                dense_vecs=[d["embedding"] for d in with_emb],
                sparse_dicts=[{} for _ in with_emb],
                metas=[d.get("meta") for d in with_emb],
            )
        # 写需要 encode 的部分
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
