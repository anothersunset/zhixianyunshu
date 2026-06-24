"""将 KB 文档索引到 RAG 服务 (Qdrant + BGE-M3)。

Usage:
    python -m eval.index_kb [--rag-url http://localhost:8001]
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

import httpx

RAG_URL_DEFAULT = "http://localhost:8001"
COLLECTION = "zhiqian-default"

# ── KB 文档：优先从统一 YAML 加载 ──
import os as _os
_KB_ROOT = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "kb"))
if _KB_ROOT not in sys.path:
    sys.path.insert(0, _os.path.dirname(_KB_ROOT))

try:
    from kb.kb_loader import load_all_docs as _load_all_docs
    _kb_docs = _load_all_docs()
    KB_DOCS: List[Dict[str, Any]] = [
        {
            "id": d["id"],
            "text": d["text"],
            "source": d.get("source", ""),
            "meta": {
                "category": d.get("category", "MISC"),
                "source_dialect": d.get("source_dialect", ""),
                "target_dialect": d.get("target_dialect", ""),
            },
        }
        for d in _kb_docs
    ]
    # DEMO_DOCS 已合并到统一 YAML 中，无需单独维护
    DEMO_DOCS: List[Dict[str, Any]] = []
except Exception:
    # 回退到硬编码（保持向后兼容）
    KB_DOCS: List[Dict[str, Any]] = []  # 将由下方的回退列表填充
    DEMO_DOCS: List[Dict[str, Any]] = [
        {
            "id": "doc-1",
            "text": (
                "openGauss 不支持 MySQL 的 DATE_FORMAT 函数,需要使用 TO_CHAR 进行格式化。"
                "例如 TO_CHAR(t.created_at, 'YYYY-MM')。格式说明符也不同：%Y→YYYY, %m→MM, %d→DD。"
            ),
            "source": "opengauss/dialect-cheatsheet.md#date-format",
            "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
        },
        {
            "id": "doc-2",
            "text": (
                "MySQL IFNULL(x, y) 在 openGauss 中可以等价替换为 COALESCE(x, y),两者语义一致。"
                "COALESCE 是 SQL 标准函数,支持多个参数: COALESCE(a, b, c) 返回第一个非 NULL 值。"
            ),
            "source": "opengauss/dialect-cheatsheet.md#null-handling",
            "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
        },
        {
            "id": "doc-3",
            "text": (
                "从 MySQL 迁移到 openGauss 时,JDBC URL 需从 jdbc:mysql:// 改为 jdbc:opengauss://,"
                "默认端口从 3306 变为 5432。驱动类从 com.mysql.cj.jdbc.Driver 改为 org.opengauss.Driver。"
            ),
            "source": "opengauss/migration-guide.md#jdbc",
            "meta": {"dialect": "openGauss", "category": "CONFIG"},
        },
        {
            "id": "doc-4",
            "text": (
                "openGauss 驱动 GA 版本仅提供 opengauss-jdbc artifact,在 Maven 中需替换 mysql-connector-java。"
                "Maven 坐标: org.opengauss:opengauss-jdbc:版本号。Gradle 也需同步更新依赖。"
            ),
            "source": "opengauss/migration-guide.md#dependency",
            "meta": {"dialect": "openGauss", "category": "DEPENDENCY"},
        },
        {
            "id": "doc-5",
            "text": (
                "建议使用 LIMIT ... OFFSET ... 并明确指定 ORDER BY,openGauss 与 MySQL 在分页语法上兼容,"
                "但顺序需明确。MySQL LIMIT 10, 20 需改写为 LIMIT 20 OFFSET 10 (注意参数顺序反转)。"
            ),
            "source": "opengauss/dialect-cheatsheet.md#pagination",
            "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
        },
        {
            "id": "doc-6",
            "text": (
                "BigDecimal 推荐映射为 openGauss 的 NUMERIC(p, s),例如金额使用 NUMERIC(20, 4),避免精度丢失。"
                "MySQL FLOAT/DOUBLE 是近似类型,迁移时应改为 NUMERIC 以保证精确计算。"
            ),
            "source": "opengauss/type-mapping.md#numeric",
        },
    ]


def index_docs(rag_url: str, docs: List[Dict[str, Any]], strategy: str = "none") -> dict:
    """调用 RAG /ingest 端点索引文档。"""
    payload = {
        "collection": COLLECTION,
        "docs": docs,
        "strategy": strategy,
    }
    resp = httpx.post(f"{rag_url}/ingest", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Index KB docs to RAG service")
    parser.add_argument("--rag-url", default=RAG_URL_DEFAULT, help="RAG service URL")
    parser.add_argument("--strategy", default="none", help="Chunking strategy: none/semantic/late")
    args = parser.parse_args()

    all_docs = KB_DOCS + DEMO_DOCS
    print(f"Indexing {len(all_docs)} docs ({len(KB_DOCS)} KB + {len(DEMO_DOCS)} demo) to {args.rag_url}...")

    result = index_docs(args.rag_url, all_docs, strategy=args.strategy)
    print(f"OK: docs_received={result['docs_received']}, chunks_inserted={result['chunks_inserted']}, "
          f"strategy={result['strategy_used']}")
    print(f"Capabilities: {json.dumps(result['capabilities'], indent=2)}")


if __name__ == "__main__":
    main()
