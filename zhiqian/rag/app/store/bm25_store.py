from typing import List, Dict, Tuple
from rank_bm25 import BM25Okapi
import jieba

class Bm25Store:
    """简易内存 BM25 索引；M4 可替换为持久存储实现。"""

    def __init__(self):
        self._indices: Dict[str, BM25Okapi] = {}
        self._ids: Dict[str, List[str]] = {}

    def index(self, name: str, docs: List[Dict[str, str]]):
        ids = [d["id"] for d in docs]
        tokenized = [list(jieba.cut(d["text"])) for d in docs]
        self._indices[name] = BM25Okapi(tokenized)
        self._ids[name] = ids

    def query(self, name: str, query: str, k: int = 50) -> List[Tuple[str, float]]:
        if name not in self._indices:
            return []
        bm25 = self._indices[name]
        scores = bm25.get_scores(list(jieba.cut(query)))
        ranked = sorted(zip(self._ids[name], scores), key=lambda x: x[1], reverse=True)
        return ranked[:k]
