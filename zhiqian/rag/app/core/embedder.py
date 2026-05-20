from __future__ import annotations
import hashlib
from typing import List, Sequence

class Embedder:
    """M4 接 BGE-M3；M2 先用确定性 hash 返回 384 维向量作为占位。"""

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self._real = None

    def encode(self, texts: Sequence[str]) -> List[List[float]]:
        if self._real is not None:
            return self._real.encode(list(texts)).tolist()
        return [self._stub(t) for t in texts]

    @staticmethod
    def _stub(text: str) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in h[:48]] * 8  # 384 dims
