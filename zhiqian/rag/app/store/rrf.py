"""Reciprocal Rank Fusion (RRF) — 业界标准的多路检索合并算法。

v2-step-05 新增。RRF 不依赖底层检索的分数尺度，只看排名，鲁棒稳定。
公式：score_rrf(d) = Σ_i w_i / (k + rank_i(d))
- k 默认 60（论文推荐值）
- 某个路径拿不到该 doc 时不贡献分数
- weights: 各渠道权重，默认 None 表示等权（全 1.0）
"""
from __future__ import annotations
from typing import Dict, Iterable, List, Optional, Tuple


def rrf_merge(
    ranked_lists: Iterable[List[Tuple[str, float]]],
    k: int = 60,
    top_n: int = 50,
    weights: Optional[List[float]] = None,
) -> List[Tuple[str, float, Dict[str, float]]]:
    """Merge multiple ranked lists with weighted RRF.

    Args:
        ranked_lists: 多路检索结果，每路是已排序的 (doc_id, score)。顺序=排名。
        k: RRF 超参，默认 60。
        top_n: 结果保留个数。
        weights: 各渠道权重列表，长度应与 ranked_lists 数量一致。
                 None 表示等权（全 1.0）。
    Returns:
        [(doc_id, fused_score, per_channel_ranks{channel_idx_str: rank}), ...]
    """
    # 将 ranked_lists 转为 list 以便多次遍历
    lists = list(ranked_lists)
    n_channels = len(lists)

    # 处理权重
    if weights is None:
        channel_weights = [1.0] * n_channels
    else:
        assert len(weights) == n_channels, f"weights length {len(weights)} != n_channels {n_channels}"
        channel_weights = weights

    import logging
    log = logging.getLogger(__name__)
    log.warning("[rrf_merge] n_channels=%d, weights=%s, channel_weights=%s, k=%d", n_channels, weights, channel_weights, k)

    fused: Dict[str, float] = {}
    channels_meta: Dict[str, Dict[str, float]] = {}
    for ch_idx, rl in enumerate(lists):
        w = channel_weights[ch_idx]
        for rank, (doc_id, _score) in enumerate(rl):
            inc = w / (k + rank + 1)  # rank 1-based
            fused[doc_id] = fused.get(doc_id, 0.0) + inc
            channels_meta.setdefault(doc_id, {})[str(ch_idx)] = float(rank + 1)
    items = sorted(fused.items(), key=lambda x: x[1], reverse=True)
    return [(doc_id, score, channels_meta.get(doc_id, {})) for doc_id, score in items[:top_n]]
