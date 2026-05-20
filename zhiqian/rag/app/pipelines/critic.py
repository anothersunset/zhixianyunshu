from __future__ import annotations

from typing import List, Dict, Any, Optional
import statistics


class SelfRagCritic:
    """
    Self-RAG critic的轻量实现：依据检索结果的得分、多样性、来源交叉覆盖率评估上下文质量。
    实际生产环境可接入 LLM 调用 (e.g. GLM-4-Plus) 完成 self-reflection。
    """

    def critique(self, question: str, chunks: List[Dict[str, Any]],
                 llm: Optional[Any] = None) -> Dict[str, Any]:
        if not chunks:
            return {
                "score": 0.0,
                "verdict": "INSUFFICIENT",
                "reasons": ["未检索到任何相关上下文"],
                "suggest_rewrite": True,
            }

        scores = [c.get("score", 0.0) for c in chunks]
        avg = float(statistics.fmean(scores)) if scores else 0.0
        spread = float(max(scores) - min(scores)) if len(scores) > 1 else 0.0
        sources = {c.get("source", "").split("#")[0] for c in chunks}
        coverage = len(sources)

        norm = min(1.0, avg / 5.0)
        diversity = min(1.0, coverage / 3.0)
        relevance = 0.6 * norm + 0.4 * diversity

        if relevance >= 0.7:
            verdict = "SUPPORTED"
        elif relevance >= 0.4:
            verdict = "PARTIAL"
        else:
            verdict = "INSUFFICIENT"

        reasons: List[str] = []
        if avg < 1.0:
            reasons.append(f"BM25 平均得分偏低 ({avg:.2f})，可能需要重写查询")
        if coverage <= 1:
            reasons.append("来源集中于单一文档，多样性不足")
        if spread > 4.0:
            reasons.append("检索得分跨度过大，尾部结果可信度偏低")
        if not reasons:
            reasons.append("上下文质量良好")

        return {
            "score": round(relevance, 3),
            "verdict": verdict,
            "reasons": reasons,
            "suggest_rewrite": verdict == "INSUFFICIENT",
            "stats": {
                "chunk_count": len(chunks),
                "avg_score": round(avg, 3),
                "source_coverage": coverage,
            },
        }
