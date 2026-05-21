"""
v2-step-12: CRAG knowledge refinement (decompose-then-recompose)。

原论文思路: 检索 doc 常含噪声 (无关句子), 直接填给 generator 会拉低质量。
解法: 把 doc 切成句子粒度 strips, 用 query 信息过滤, 重组成净净的 context。
本实现是轻量版本 (regex 句切 + keyword 过滤), 避免依赖 spaCy。
"""
from __future__ import annotations

import re
from typing import List, Dict, Any

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[\u4e00-\u9fff]")
_SENT_SPLIT_RE = re.compile(r"(?<=[\u3002\uff01\uff1f.!?])\s*")


def _tokenize(s: str) -> set:
    return {t.lower() for t in _TOKEN_RE.findall(s or "")}


class KnowledgeRefiner:
    """CRAG knowledge refinement。

    Args:
        min_strip_len: 句子最短字符数 (过滤垃圾片段)
        max_strips: 输出最多 strips 数
        min_overlap: keyword 重叠阈值 (低于此不取)
    """

    def __init__(self, min_strip_len: int = 8, max_strips: int = 20, min_overlap: float = 0.1):
        self.min_strip_len = min_strip_len
        self.max_strips = max_strips
        self.min_overlap = min_overlap

    def refine(self, question: str, docs: List[Dict[str, Any]]) -> List[str]:
        """返回按 query 相关性降序的 strips。"""
        q_tokens = _tokenize(question)
        if not q_tokens:
            # 空查询: 原样返前 5 个 doc 的文本
            return [(d.get("text") or d.get("content") or "")[:500] for d in docs[:5]]
        scored: List[tuple] = []
        for d in docs:
            text = d.get("text") or d.get("content") or ""
            for sent in self._split_sentences(text):
                if len(sent) < self.min_strip_len:
                    continue
                s_tokens = _tokenize(sent)
                if not s_tokens:
                    continue
                overlap = len(q_tokens & s_tokens) / max(len(q_tokens), 1)
                if overlap < self.min_overlap:
                    continue
                scored.append((overlap, sent))
        # 按 overlap 降序, 取 max_strips
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[: self.max_strips]]

    def _split_sentences(self, text: str) -> List[str]:
        """中英混合句切。以 。！？.!? 为边界。"""
        text = re.sub(r"\s+", " ", (text or "").strip())
        if not text:
            return []
        sents = _SENT_SPLIT_RE.split(text)
        return [s.strip() for s in sents if s and s.strip()]
