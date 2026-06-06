"""指标：SQL 修复成功率、迁移报告准确率、Recall@k。"""
from __future__ import annotations

import sqlglot

DIALECT_MAP = {
    "mysql": "mysql",
    "opengauss": "postgres",  # openGauss 方言接近 PostgreSQL
    "postgresql": "postgres",
    "postgres": "postgres",
    "oracle": "oracle",
}


def _normalize(sql: str, dialect: str) -> str | None:
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
        return tree.sql(dialect=dialect, normalize=True, pretty=False).lower().strip().rstrip(";")
    except Exception:
        return None


def sql_equivalent(pred: str, gold: str, target: str) -> bool:
    """结构等价：解析归一化后比对。无法解析返回 False，交给 LLM judge / 人工兜底。"""
    d = DIALECT_MAP.get(target, "postgres")
    np_, ng = _normalize(pred, d), _normalize(gold, d)
    if np_ is None or ng is None:
        return False
    return np_ == ng


def report_point_hit_rate(pred_points: list[str], gold_points: list[str], judge=None) -> float:
    if not gold_points:
        return 1.0
    hits = 0
    for g in gold_points:
        if judge is not None:
            if judge.point_covered(g, pred_points):
                hits += 1
        else:
            # 退化：粗粒度关键词命中（仅在没接 judge 时使用）。
            if any(g[:6] in p or p[:6] in g for p in pred_points):
                hits += 1
    return hits / len(gold_points)


def recall_at_k(retrieved_ids: list[str], gold_ids: list[str], k: int = 5) -> float:
    if not gold_ids:
        return float("nan")
    topk = set(retrieved_ids[:k])
    return len(topk & set(gold_ids)) / len(set(gold_ids))
