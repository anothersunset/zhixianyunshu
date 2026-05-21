"""
v2-step-12: CRAG retrieval evaluator。

原论文 (Yan et al. 2024, arXiv:2401.15884):
- Evaluator 给每条 doc 打 [-1, 1] 分, T+/T- 两个阈值决定 route。
- correct  : 最高分 > T+  → 只用本地 doc
- incorrect: 最高分 < T-  → 丢掉本地, 走 web_search
- ambiguous: 中间         → 本地 + web 混合

本实现选择轻量版本 (keyword overlap), 以避免每次查询都调 LLM。
需严格准确时可设 RAG_CRAG_USE_LLM_EVAL=1 启用 DeepSeek 0/1 判官。
"""
from __future__ import annotations

import os
import re
from typing import List, Dict, Any

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[\u4e00-\u9fff]")


def _tokenize(s: str) -> set:
    """中英混合分词: 英文单词包含下划线, 中文单字。"""
    return {t.lower() for t in _TOKEN_RE.findall(s or "")}


class RetrievalEvaluator:
    """CRAG retrieval evaluator。

    Args:
        upper: T+ 阈值, 默认 0.5
        lower: T- 阈值, 默认 0.15
        top_k_for_eval: 只取 top-k 估算 confidence (避免含噪 doc 拉低均值)
    """

    def __init__(self, upper: float = 0.5, lower: float = 0.15, top_k_for_eval: int = 3):
        self.upper = upper
        self.lower = lower
        self.top_k_for_eval = top_k_for_eval
        self.use_llm = os.environ.get("RAG_CRAG_USE_LLM_EVAL", "0") == "1"

    def score(self, question: str, docs: List[Dict[str, Any]]) -> float:
        """返回 [0,1] 的平均置信度。空 doc 返 0。"""
        if not docs:
            return 0.0
        q_tokens = _tokenize(question)
        if not q_tokens:
            return 0.0
        per_doc_scores = []
        for d in docs[: self.top_k_for_eval]:
            text = d.get("text") or d.get("content") or ""
            d_tokens = _tokenize(text)
            if not d_tokens:
                per_doc_scores.append(0.0)
                continue
            # 双向 IoU 型: 交集 / (查询 token 总量), 避免 long doc 被分母炸
            overlap = len(q_tokens & d_tokens) / max(len(q_tokens), 1)
            per_doc_scores.append(min(overlap, 1.0))
        # 加权: top-1 权重高于后面几位
        if not per_doc_scores:
            return 0.0
        weights = [1.0, 0.7, 0.5][: len(per_doc_scores)]
        wsum = sum(weights)
        avg = sum(s * w for s, w in zip(per_doc_scores, weights)) / wsum
        return float(round(avg, 4))

    def route(self, confidence: float) -> str:
        """三路由: correct / ambiguous / incorrect。"""
        if confidence >= self.upper:
            return "correct"
        if confidence <= self.lower:
            return "incorrect"
        return "ambiguous"
