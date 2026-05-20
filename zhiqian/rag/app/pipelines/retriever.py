from __future__ import annotations

from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
import re

# 轻量内存 BM25＋TF伪嵌入的混合检索器。
# 本地部署未接入 BGE-M3 / Faiss 时依然可运行，足以演示 Self-RAG 流程。


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
    return [t for t in re.split(r"[\s,.;:!?()\[\]{}<>=#'\"\u3002\uff0c\uff1b\uff1a\uff01\uff1f\u3001]+", text.lower()) if t]


class HybridRetriever:
    def __init__(self, docs: Optional[List[Dict[str, Any]]] = None):
        self.docs = docs if docs is not None else _DEMO_DOCS
        self._tokens = [_tokenize(d["text"]) for d in self.docs]
        self._bm25 = BM25Okapi(self._tokens) if self._tokens else None

    def search(self, question: str, top_k: int = 5,
               filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self.docs or self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(question))
        ranked = sorted(
            zip(scores, self.docs),
            key=lambda x: x[0],
            reverse=True,
        )
        results: List[Dict[str, Any]] = []
        for score, d in ranked:
            if filters:
                meta = d.get("meta") or {}
                if any(meta.get(k) != v for k, v in filters.items()):
                    continue
            results.append({
                "id": d["id"],
                "text": d["text"],
                "score": float(score),
                "source": d.get("source", "unknown"),
                "meta": d.get("meta"),
            })
            if len(results) >= top_k:
                break
        return results
