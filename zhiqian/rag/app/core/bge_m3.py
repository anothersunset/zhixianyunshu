"""BGE-M3 lazy wrapper.

v2-step-04 新增。设计原则：
- 仅在首次 encode 时才加载模型（lazy load），启动不阻塞。
- FlagEmbedding 未安装时降级为 1024 维确定性 hash 向量，什么都不报错。
- 同时返回 dense + sparse + colbert 三路向量，供未来接 Qdrant 混合索引使用。
安装真实模型：在 zhiqian/rag/ 下执行 `pip install -r requirements-ml.txt`，
或 docker build 时传 --build-arg BUILD_ML=1。
"""
from __future__ import annotations
import hashlib
import logging
from typing import Any, Dict, List, Optional, Sequence

log = logging.getLogger(__name__)


class BgeM3Embedder:
    """BAAI/bge-m3 向量化编码器。"""

    def __init__(
        self,
        model_path: str = "BAAI/bge-m3",
        use_fp16: bool = True,
        device: Optional[str] = None,
        dim: int = 1024,
    ):
        self.model_path = model_path
        self.use_fp16 = use_fp16
        self.device = device
        self.dim = dim
        self._model = None
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                from FlagEmbedding import BGEM3FlagModel  # noqa: F401
                self._available = True
            except ImportError:
                log.warning(
                    "[BGE-M3] FlagEmbedding 未安装，使用 1024 维 hash 占位向量。"
                    "安装真实模型：pip install -r requirements-ml.txt"
                )
                self._available = False
        return self._available

    def _load(self):
        if self._model is not None:
            return self._model
        from FlagEmbedding import BGEM3FlagModel
        log.info("[BGE-M3] 加载模型 path=%s use_fp16=%s", self.model_path, self.use_fp16)
        kwargs: Dict[str, Any] = {"use_fp16": self.use_fp16}
        if self.device:
            kwargs["devices"] = [self.device]
        self._model = BGEM3FlagModel(self.model_path, **kwargs)
        return self._model

    def encode_dense(self, texts: Sequence[str]) -> List[List[float]]:
        if not self.available:
            return [_hash_vec(t, self.dim) for t in texts]
        m = self._load()
        out = m.encode(list(texts), return_dense=True, return_sparse=False, return_colbert_vecs=False)
        return [list(map(float, v)) for v in out["dense_vecs"]]

    def encode_full(self, texts: Sequence[str]) -> Dict[str, Any]:
        """返回 dense / sparse / colbert 三路向量。fallback 时 sparse 为空、colbert 为空列表。"""
        if not self.available:
            return {
                "dense_vecs": [_hash_vec(t, self.dim) for t in texts],
                "lexical_weights": [{} for _ in texts],
                "colbert_vecs": [[] for _ in texts],
            }
        m = self._load()
        out = m.encode(
            list(texts), return_dense=True, return_sparse=True, return_colbert_vecs=True
        )
        return {
            "dense_vecs": [list(map(float, v)) for v in out["dense_vecs"]],
            "lexical_weights": out["lexical_weights"],
            "colbert_vecs": [[list(map(float, v)) for v in cv] for cv in out["colbert_vecs"]],
        }


def _hash_vec(text: str, dim: int) -> List[float]:
    h = hashlib.sha256((text or "").encode("utf-8")).digest()
    base = [b / 255.0 for b in h]
    needed = (dim // len(base)) + 1
    return (base * needed)[:dim]
