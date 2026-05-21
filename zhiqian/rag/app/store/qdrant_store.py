"""Qdrant 向量库封装。

v2-step-05 新增。设计原则：
- qdrant-client 未装 或 URL 不可达时 available=False，上层退化到 Chroma + BM25。
- 同一 collection 同时存 dense (1024) + sparse (BGE-M3 lexical_weights) 向量。
- 未启用也能避免 import 出错。
启用方式： docker compose --profile ml up -d  + RAG_USE_QDRANT=true
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class QdrantStore:
    def __init__(self, url: str = "http://qdrant:6333", api_key: Optional[str] = None, dim: int = 1024):
        self.url = url
        self.api_key = api_key
        self.dim = dim
        self._client = None
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                from qdrant_client import QdrantClient  # noqa: F401
                self._available = True
            except ImportError:
                log.warning("[Qdrant] qdrant-client 未安装，跳过 Qdrant 底层。安装：pip install -r requirements-ml.txt")
                self._available = False
        return self._available

    def _get_client(self):
        if self._client is not None:
            return self._client
        from qdrant_client import QdrantClient
        log.info("[Qdrant] 连接 %s", self.url)
        kwargs: Dict[str, Any] = {"url": self.url, "timeout": 10.0}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        self._client = QdrantClient(**kwargs)
        return self._client

    def ensure_collection(self, name: str) -> bool:
        """创建同时含 dense + sparse 向量的 collection。重复创建是 no-op。"""
        if not self.available:
            return False
        try:
            from qdrant_client.http import models as qm
            c = self._get_client()
            existing = {col.name for col in c.get_collections().collections}
            if name in existing:
                return True
            c.create_collection(
                collection_name=name,
                vectors_config={"dense": qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE)},
                sparse_vectors_config={"sparse": qm.SparseVectorParams(index=qm.SparseIndexParams(on_disk=False))},
            )
            log.info("[Qdrant] 创建 collection=%s dim=%d (dense+sparse)", name, self.dim)
            return True
        except Exception as e:
            log.warning("[Qdrant] ensure_collection 失败 name=%s err=%s", name, e)
            return False

    def upsert(
        self,
        name: str,
        ids: List[str],
        texts: List[str],
        dense_vecs: List[List[float]],
        sparse_dicts: Optional[List[Dict[int, float]]] = None,
        metas: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if not self.available or not self.ensure_collection(name):
            return False
        try:
            from qdrant_client.http import models as qm
            c = self._get_client()
            points = []
            for i, (pid, text, dense) in enumerate(zip(ids, texts, dense_vecs)):
                payload: Dict[str, Any] = {"text": text, "id_str": pid}
                if metas and i < len(metas):
                    payload["meta"] = metas[i] or {}
                vec: Dict[str, Any] = {"dense": dense}
                if sparse_dicts and i < len(sparse_dicts) and sparse_dicts[i]:
                    sd = sparse_dicts[i]
                    vec["sparse"] = qm.SparseVector(indices=list(sd.keys()), values=list(sd.values()))
                points.append(qm.PointStruct(id=_to_qdrant_id(pid), vector=vec, payload=payload))
            c.upsert(collection_name=name, points=points)
            log.info("[Qdrant] upsert collection=%s count=%d", name, len(points))
            return True
        except Exception as e:
            log.warning("[Qdrant] upsert 失败 name=%s err=%s", name, e)
            return False

    def search_dense(self, name: str, dense: List[float], k: int = 50) -> List[Tuple[str, float, Dict[str, Any]]]:
        if not self.available:
            return []
        try:
            from qdrant_client.http import models as qm
            c = self._get_client()
            res = c.query_points(
                collection_name=name,
                query=dense,
                using="dense",
                limit=k,
                with_payload=True,
            ).points
            return [(_extract_id(p), float(p.score), dict(p.payload or {})) for p in res]
        except Exception as e:
            log.warning("[Qdrant] search_dense 失败 name=%s err=%s", name, e)
            return []

    def search_sparse(self, name: str, sparse: Dict[int, float], k: int = 50) -> List[Tuple[str, float, Dict[str, Any]]]:
        if not self.available or not sparse:
            return []
        try:
            from qdrant_client.http import models as qm
            c = self._get_client()
            res = c.query_points(
                collection_name=name,
                query=qm.SparseVector(indices=list(sparse.keys()), values=list(sparse.values())),
                using="sparse",
                limit=k,
                with_payload=True,
            ).points
            return [(_extract_id(p), float(p.score), dict(p.payload or {})) for p in res]
        except Exception as e:
            log.warning("[Qdrant] search_sparse 失败 name=%s err=%s", name, e)
            return []


def _to_qdrant_id(s: str) -> str:
    """Qdrant point id 接受 uuid 或 unsigned int。这里用一个确定性 uuid-like 字符串。"""
    import hashlib
    h = hashlib.md5(s.encode("utf-8")).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _extract_id(point) -> str:
    payload = getattr(point, "payload", None) or {}
    return payload.get("id_str") or str(getattr(point, "id", ""))
