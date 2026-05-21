"""bge-reranker-v2-m3 cross-encoder lazy wrapper.

v2-step-04 新增。同样 lazy load + 优雅降级。
- 真模式：FlagEmbedding.FlagReranker 返回 query-doc 对的相关性 score。
- 降级模式：按原顺序的 BM25 头部截断。
"""
from __future__ import annotations
import logging
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)


class CrossEncoderReranker:
    def __init__(
        self,
        model_path: str = "BAAI/bge-reranker-v2-m3",
        use_fp16: bool = True,
        device: Optional[str] = None,
    ):
        self.model_path = model_path
        self.use_fp16 = use_fp16
        self.device = device
        self._model = None
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                from FlagEmbedding import FlagReranker  # noqa: F401
                self._available = True
            except ImportError:
                log.warning(
                    "[Reranker] FlagEmbedding 未安装，重排退化为原顺序截断。"
                    "启用真实重排：pip install -r requirements-ml.txt"
                )
                self._available = False
        return self._available

    def _load(self):
        if self._model is not None:
            return self._model
        from FlagEmbedding import FlagReranker
        log.info("[Reranker] 加载模型 path=%s use_fp16=%s", self.model_path, self.use_fp16)
        kwargs = {"use_fp16": self.use_fp16}
        if self.device:
            kwargs["devices"] = [self.device]
        self._model = FlagReranker(self.model_path, **kwargs)
        return self._model

    def rerank(self, query: str, candidates: List[str], top_n: int = 5) -> List[Tuple[int, float]]:
        """返回 [(原始下标, score), …] 按 score 倒序、最多 top_n。"""
        if not candidates:
            return []
        if not self.available:
            return [(i, 1.0 - i * 0.01) for i in range(min(top_n, len(candidates)))]
        m = self._load()
        pairs = [[query, c] for c in candidates]
        raw = m.compute_score(pairs, normalize=True)
        if not isinstance(raw, list):
            raw = [raw]
        ranked = sorted(enumerate(raw), key=lambda x: float(x[1]), reverse=True)
        return [(i, float(s)) for i, s in ranked[:top_n]]
