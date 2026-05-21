"""通用向量化接口。

v2-step-04 重构：低层实际委托给 BgeM3Embedder（lazy + fallback），上层调用者看到的联合接口不变。
- vector_store.py 只按 List[float] 向量底层入库，不关心具体是真 BGE 还是 hash。
- embedding_dim 默认 1024，与 BGE-M3 原生一致。
"""
from __future__ import annotations
import hashlib
from typing import List, Sequence, Optional
from app.core.bge_m3 import BgeM3Embedder


class Embedder:
    """v2-step-04：优先走 BGE-M3，不可用时降级为 1024 维 hash 占位。"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        use_bge: bool = True,
        dim: int = 1024,
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.use_bge = use_bge
        self.dim = dim
        self._bge = BgeM3Embedder(model_path=model_name, dim=dim, device=device) if use_bge else None

    @property
    def is_real(self) -> bool:
        return self._bge is not None and self._bge.available

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        if self._bge is not None and self._bge.available:
            return self._bge.encode_dense(texts)
        return [self._stub(t, self.dim) for t in texts]

    @staticmethod
    def _stub(text: str, dim: int = 1024) -> List[float]:
        h = hashlib.sha256((text or "").encode("utf-8")).digest()
        base = [b / 255.0 for b in h]
        return (base * ((dim // len(base)) + 1))[:dim]
