from typing import List, Dict, Any
from app.store.vector_store import VectorStore
from app.store.bm25_store import Bm25Store

class HybridRetriever:
    def __init__(self, vec: VectorStore, bm25: Bm25Store, alpha: float = 0.6):
        self.vec = vec
        self.bm25 = bm25
        self.alpha = alpha

    def retrieve(self, collection: str, query: str, k: int = 50) -> List[Dict[str, Any]]:
        v = self.vec.query(collection, query, k=k)
        b = self.bm25.query(collection, query, k=k)
        scores: Dict[str, Dict[str, Any]] = {}
        for r, dist in zip(v["ids"][0], v["distances"][0]):
            scores[r] = {"id": r, "vec_score": 1.0 - dist, "bm25_score": 0.0}
        for r, s in b:
            cur = scores.setdefault(r, {"id": r, "vec_score": 0.0, "bm25_score": 0.0})
            cur["bm25_score"] = s
        merged = []
        for r in scores.values():
            r["score"] = self.alpha * r["vec_score"] + (1 - self.alpha) * r["bm25_score"]
            merged.append(r)
        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged[:k]
