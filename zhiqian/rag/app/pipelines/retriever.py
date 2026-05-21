from __future__ import annotations

from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
import logging
import re

from app.config import settings
from app.core.reranker import CrossEncoderReranker

log = logging.getLogger(__name__)

# v2-step-04：BM25 粗排 + bge-reranker-v2-m3 交叉编码器精排。
# - reranker.available=true 时：BM25 拉取 top_k*5 候选，重排后取 top_k
# - false 时：退化到 v1 纯BM25 顺序，保证 0 依赖环境也能跑


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


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"[\s,.;:!?()\[\]{}<>=#'\"\u3002\uff0c\uff1b\uff1a\uff01\uff1f\u3001]+", (text or "").lower()) if t]


class HybridRetriever:
    def __init__(
        self,
        docs: Optional[List[Dict[str, Any]]] = None,
        reranker: Optional[CrossEncoderReranker] = None,
    ):
        self.docs = docs if docs is not None else _DEMO_DOCS
        self._tokens = [_tokenize(d["text"]) for d in self.docs]
        self._bm25 = BM25Okapi(self._tokens) if self._tokens else None
        if reranker is not None:
            self._reranker = reranker
        elif settings.use_reranker:
            self._reranker = CrossEncoderReranker(
                model_path=settings.reranker_model, use_fp16=settings.reranker_fp16
            )
        else:
            self._reranker = None
        if self._reranker is not None:
            log.info(
                "[HybridRetriever] reranker=%s, available=%s",
                settings.reranker_model,
                self._reranker.available,
            )

    def search(
        self,
        question: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.docs or self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(question))
        ranked = sorted(zip(scores, self.docs), key=lambda x: x[0], reverse=True)
        # 粗排：多取一些候选给交叉编码器重排
        coarse_k = max(top_k * 5, top_k)
        coarse: List[Dict[str, Any]] = []
        for bm25_score, d in ranked:
            if filters:
                meta = d.get("meta") or {}
                if any(meta.get(k) != v for k, v in filters.items()):
                    continue
            coarse.append({
                "id": d["id"],
                "text": d["text"],
                "score": float(bm25_score),
                "bm25_score": float(bm25_score),
                "source": d.get("source", "unknown"),
                "meta": d.get("meta"),
            })
            if len(coarse) >= coarse_k:
                break
        if not coarse:
            return []
        # 精排
        if self._reranker is not None and self._reranker.available:
            texts = [c["text"] for c in coarse]
            reranked = self._reranker.rerank(question, texts, top_n=top_k)
            results: List[Dict[str, Any]] = []
            for idx, rscore in reranked:
                item = dict(coarse[idx])
                item["rerank_score"] = float(rscore)
                item["score"] = float(rscore)  # 上层 score 面向“最后的分”语义
                results.append(item)
            return results
        # 退化：直接取 BM25 前 top_k
        return coarse[:top_k]
