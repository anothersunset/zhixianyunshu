"""Chunking 策略：SemanticChunker / LateChunker。

v2-step-06 新增。Late Chunking 是 Jina AI 2024 提出的技术：
  “先对全文走一遍 encoder，拿到 token-level embeddings；再按 chunk 范围对 token
   做池化得到 chunk embedding。这样每个 chunk 的表示都携带了全文上下文。”
与传统先切后 embed 相比，召回、NDCG 提升 5–10％。

SemanticChunker：
- 切句后逐句 embed，计算相邻句的 cosine；相似度 < 阈值 或 累计字数超上限时切块。
- 不需 BGE 也能跑（fallback hash 向量）。
LateChunker：
- 全文 encode_full 拿 colbert_vecs；字符窗口切块，用 char→token 近似映射取范围后平均。
- BGE 不可用时退化为纯字符窗口 + hash。
两个 Chunker 返回同样的 schema：
  { id, text, meta: {strategy, parent_id, chunk_index, ...}, embedding?: List[float] }
调用者如果看到 embedding 字段存在，应使用它代替重新 encode。
"""
from __future__ import annotations
import logging
import math
from typing import Any, Dict, List, Optional

from app.core.bge_m3 import BgeM3Embedder, _hash_vec
from app.core.sentence_splitter import split_sentences

log = logging.getLogger(__name__)


def _cosine(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a[:n]))
    nb = math.sqrt(sum(y * y for y in b[:n]))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def _vec_mean(vecs: List[List[float]], dim: int) -> List[float]:
    if not vecs:
        return [0.0] * dim
    out = [0.0] * dim
    for v in vecs:
        for i in range(min(dim, len(v))):
            out[i] += v[i]
    n = float(len(vecs))
    return [x / n for x in out]


class SemanticChunker:
    """语义分块：句子粒度 + 相邻句相似度合并。"""

    def __init__(
        self,
        embedder: Optional[BgeM3Embedder] = None,
        sim_threshold: float = 0.62,
        max_chars: int = 1200,
        min_chars: int = 80,
        dim: int = 1024,
    ):
        self.embedder = embedder
        self.sim_threshold = sim_threshold
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.dim = dim

    def chunk(self, text: str, doc_id: str = "") -> List[Dict[str, Any]]:
        sents = split_sentences(text)
        if not sents:
            return []
        if len(sents) == 1 or len(text) <= self.max_chars:
            # 不需切
            return [self._wrap(doc_id, 0, text, embedding=None, sim_to_prev=None)]
        # 逐句 embed
        if self.embedder is not None and self.embedder.available:
            sent_vecs = self.embedder.encode_dense(sents)
        else:
            sent_vecs = [_hash_vec(s, self.dim) for s in sents]
        # 合并
        chunks_text: List[str] = []
        chunks_sims: List[Optional[float]] = []
        cur_sents = [sents[0]]
        cur_chars = len(sents[0])
        for i in range(1, len(sents)):
            sim = _cosine(sent_vecs[i - 1], sent_vecs[i])
            need_break = (
                cur_chars + len(sents[i]) > self.max_chars or sim < self.sim_threshold
            ) and cur_chars >= self.min_chars
            if need_break:
                chunks_text.append(" ".join(cur_sents))
                chunks_sims.append(sim)
                cur_sents = [sents[i]]
                cur_chars = len(sents[i])
            else:
                cur_sents.append(sents[i])
                cur_chars += len(sents[i])
        chunks_text.append(" ".join(cur_sents))
        chunks_sims.append(None)
        return [
            self._wrap(doc_id, i, t, embedding=None, sim_to_prev=s)
            for i, (t, s) in enumerate(zip(chunks_text, chunks_sims))
        ]

    def _wrap(self, doc_id: str, idx: int, text: str, embedding, sim_to_prev) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": f"{doc_id}::sc-{idx}" if doc_id else f"sc-{idx}",
            "text": text,
            "meta": {
                "strategy": "semantic",
                "parent_id": doc_id,
                "chunk_index": idx,
                "sim_threshold": self.sim_threshold,
            },
        }
        if sim_to_prev is not None:
            out["meta"]["sim_to_prev"] = float(sim_to_prev)
        if embedding is not None:
            out["embedding"] = embedding
        return out


class LateChunker:
    """Late Chunking：全文 encode + 按 chunk 范围池化 token 向量。"""

    def __init__(
        self,
        embedder: Optional[BgeM3Embedder] = None,
        max_chars: int = 600,
        overlap_chars: int = 80,
        dim: int = 1024,
    ):
        self.embedder = embedder
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars
        self.dim = dim

    def chunk(self, text: str, doc_id: str = "") -> List[Dict[str, Any]]:
        if not text:
            return []
        # 字符滑窗切块
        spans: List[tuple] = []
        i = 0
        n = len(text)
        while i < n:
            j = min(i + self.max_chars, n)
            spans.append((i, j))
            if j == n:
                break
            i = max(j - self.overlap_chars, i + 1)
        # 全文 encode_full 取 colbert_vecs
        chunk_embs: List[Optional[List[float]]] = [None] * len(spans)
        if self.embedder is not None and self.embedder.available:
            try:
                full = self.embedder.encode_full([text])
                colbert = full["colbert_vecs"][0]  # List[List[float]] of len token_count
                token_count = len(colbert)
                if token_count > 0:
                    tokens_per_char = token_count / float(n)
                    for k, (a, b) in enumerate(spans):
                        t_a = max(0, int(math.floor(a * tokens_per_char)))
                        t_b = min(token_count, max(t_a + 1, int(math.ceil(b * tokens_per_char))))
                        chunk_embs[k] = _vec_mean(colbert[t_a:t_b], self.dim)
            except Exception as e:
                log.warning("[LateChunker] colbert 路径失败 err=%s, 退化为 hash", e)
        # 组装
        out: List[Dict[str, Any]] = []
        for k, (a, b) in enumerate(spans):
            piece = text[a:b]
            emb = chunk_embs[k]
            if emb is None:
                emb = _hash_vec(piece, self.dim)
            out.append({
                "id": f"{doc_id}::lc-{k}" if doc_id else f"lc-{k}",
                "text": piece,
                "meta": {
                    "strategy": "late",
                    "parent_id": doc_id,
                    "chunk_index": k,
                    "char_range": [a, b],
                    "max_chars": self.max_chars,
                    "overlap_chars": self.overlap_chars,
                },
                "embedding": emb,
            })
        return out


def pick_chunker(
    strategy: str,
    embedder: Optional[BgeM3Embedder] = None,
    sim_threshold: float = 0.62,
    max_chars: int = 1200,
    late_max_chars: int = 600,
    late_overlap: int = 80,
    dim: int = 1024,
):
    s = (strategy or "").lower()
    if s == "late":
        return LateChunker(embedder=embedder, max_chars=late_max_chars, overlap_chars=late_overlap, dim=dim)
    if s in ("semantic", "", "default"):
        return SemanticChunker(embedder=embedder, sim_threshold=sim_threshold, max_chars=max_chars, dim=dim)
    if s == "none":
        return None
    log.warning("[pick_chunker] 未知策略=%s, 退化为 semantic", strategy)
    return SemanticChunker(embedder=embedder, sim_threshold=sim_threshold, max_chars=max_chars, dim=dim)
