"""Collection-aware, mode-explicit retrieval pipeline.

This module is intentionally independent from optional ML packages.  Dense,
sparse and reranking channels are enabled only when their injected adapters are
available; the trace reports every degraded channel so an ablation run cannot
silently claim a capability that did not execute.
"""
from __future__ import annotations

import logging
import re
import threading
from contextlib import ExitStack
from typing import Any, Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

from app.config import settings
from app.core.bge_m3 import BgeM3Embedder
from app.core.observability import get_langfuse
from app.core.reranker import CrossEncoderReranker
from app.graphs.evaluator import RetrievalEvaluator
from app.pipelines.rewriter import QueryRewriter
from app.store.qdrant_store import QdrantStore
from app.store.rrf import rrf_merge

from .retriever import _DEMO_COLLECTION, _load_kb_docs, _tokenize

log = logging.getLogger(__name__)

_COLLECTION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MODE_MAP = {
    "bm25": "bm25",
    "hybrid": "hybrid",
    "rerank": "rerank",
    "crag": "crag",
    "full": "full",
    # One-release compatibility aliases used by the existing eval scripts.
    "vector": "dense",
    "vector_rerank": "dense_rerank",
}


def validate_collection_name(name: str) -> str:
    value = (name or "").strip()
    if not _COLLECTION_RE.fullmatch(value):
        raise ValueError(
            "collection must start with an alphanumeric character and contain "
            "only alphanumerics, '.', '_' or '-' (maximum 128 characters)"
        )
    return value


def normalize_mode(mode: str) -> str:
    value = (mode or "").strip().lower()
    try:
        return _MODE_MAP[value]
    except KeyError as exc:
        raise ValueError(
            "unsupported retrieval mode; expected one of: "
            + ", ".join(_MODE_MAP)
        ) from exc


def _matches_filters(doc: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    if not filters:
        return True
    meta = doc.get("meta") or {}
    for key, expected in filters.items():
        actual = meta.get(key)
        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


class HybridRetriever:
    """Five-mode retriever with strict in-memory and Qdrant collection isolation."""

    def __init__(
        self,
        docs: Optional[List[Dict[str, Any]]] = None,
        reranker: Optional[CrossEncoderReranker] = None,
        embedder: Optional[BgeM3Embedder] = None,
        qdrant: Optional[QdrantStore] = None,
        collection: str = _DEMO_COLLECTION,
        evaluator: Optional[RetrievalEvaluator] = None,
        rewriter: Optional[QueryRewriter] = None,
    ) -> None:
        self._lock = threading.RLock()
        self.collection = validate_collection_name(collection)
        initial_docs = list(docs) if docs is not None else _load_kb_docs()
        self._collections: Dict[str, Dict[str, Any]] = {
            self.collection: self._build_state(initial_docs)
        }
        self._sync_default_attributes()

        self._reranker = reranker
        if self._reranker is None and settings.use_reranker:
            self._reranker = CrossEncoderReranker(
                model_path=settings.reranker_model,
                use_fp16=settings.reranker_fp16,
            )
        self._embedder = embedder
        if self._embedder is None and settings.use_bge_m3:
            self._embedder = BgeM3Embedder(
                model_path=settings.bge_model,
                use_fp16=settings.bge_fp16,
                dim=settings.embedding_dim,
            )
        self._qdrant = qdrant
        if self._qdrant is None and settings.use_qdrant:
            self._qdrant = QdrantStore(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
                dim=settings.embedding_dim,
                local_path=settings.qdrant_local_path or None,
            )

        self._evaluator = evaluator or RetrievalEvaluator()
        self._rewriter = rewriter or QueryRewriter()
        self.graph_index: Any = None  # default collection; populated by main.py
        self._graph_indexes: Dict[str, Any] = {}

        log.info(
            "[HybridRetriever] collection=%s docs=%d dense=%s sparse=%s rerank=%s",
            self.collection,
            len(self.docs),
            self._dense_available(),
            self._dense_available(),
            self._rerank_available(),
        )
        self._maybe_seed_qdrant(self.collection)

    @staticmethod
    def _build_state(docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        clean_docs: List[Dict[str, Any]] = []
        by_id: Dict[str, Dict[str, Any]] = {}
        for raw in docs:
            doc_id = str(raw.get("id") or "").strip()
            text = str(raw.get("text") or "")
            if not doc_id or doc_id in by_id:
                continue
            doc = {**raw, "id": doc_id, "text": text}
            clean_docs.append(doc)
            by_id[doc_id] = doc
        tokens = [_tokenize(doc["text"]) for doc in clean_docs]
        bm25 = BM25Okapi(tokens) if clean_docs and any(tokens) else None
        return {"docs": clean_docs, "by_id": by_id, "tokens": tokens, "bm25": bm25}

    def _sync_default_attributes(self) -> None:
        """Keep the historical attributes used by graph builders and diagnostics."""
        state = self._collections[self.collection]
        self.docs = state["docs"]
        self._by_id = state["by_id"]
        self._tokens = state["tokens"]
        self._bm25 = state["bm25"]

    def _state(self, collection: str, *, create: bool = False) -> Optional[Dict[str, Any]]:
        name = validate_collection_name(collection)
        state = self._collections.get(name)
        if state is None and create:
            state = self._build_state([])
            self._collections[name] = state
        return state

    def add(self, docs: List[Dict[str, Any]], collection: Optional[str] = None) -> int:
        if not docs:
            return 0
        name = validate_collection_name(collection or self.collection)
        added: List[Dict[str, Any]] = []
        with self._lock:
            state = self._state(name, create=True)
            assert state is not None
            for raw in docs:
                doc_id = str(raw.get("id") or "").strip()
                if not doc_id or doc_id in state["by_id"]:
                    continue
                doc = {**raw, "id": doc_id, "text": str(raw.get("text") or "")}
                state["docs"].append(doc)
                state["by_id"][doc_id] = doc
                added.append(doc)
            state["tokens"] = [_tokenize(doc["text"]) for doc in state["docs"]]
            state["bm25"] = (
                BM25Okapi(state["tokens"])
                if state["docs"] and any(state["tokens"])
                else None
            )
            if name == self.collection:
                self._sync_default_attributes()
            if name == self.collection:
                self.graph_index = None
            self._graph_indexes.pop(name, None)
        self._index_qdrant(added, name)
        return len(added)

    def search(
        self,
        question: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        mode: str = "full",
        parent_trace: Any = None,
        collection: Optional[str] = None,
        trace_out: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        name = validate_collection_name(collection or self.collection)
        internal_mode = normalize_mode(mode)
        top_k = max(1, min(int(top_k), 50))
        state = self._state(name)
        trace: Dict[str, Any] = {
            "mode": mode.lower(),
            "effective_mode": internal_mode,
            "collection": name,
            "channels": [],
            "degraded_channels": [],
            "filters_pushed_down": bool(filters and self._qdrant),
            "crag": None,
            "graph": {"attempted": internal_mode == "full", "hits": 0},
        }
        if state is None or not state["docs"]:
            if trace_out is not None:
                trace_out.update(trace)
            return []

        lf = get_langfuse()
        with ExitStack() as stack:
            tr = parent_trace
            if tr is None:
                tr = stack.enter_context(
                    lf.trace(
                        "rag.retrieve",
                        input={"question": question, "top_k": top_k, "mode": mode},
                        metadata={"collection": name, "filters": filters or {}},
                        tags=["rag", "retrieve"],
                    )
                )

            coarse_k = max(top_k * 3, top_k)
            result = self._retrieve_once(
                question,
                coarse_k,
                filters,
                internal_mode,
                name,
                state,
                tr,
                trace,
            )

            if internal_mode in {"crag", "full"}:
                confidence = self._evaluator.score(question, result[:top_k])
                route = self._evaluator.route(confidence)
                crag_trace: Dict[str, Any] = {
                    "evaluated": True,
                    "confidence": confidence,
                    "route": route,
                    "rewritten_query": None,
                }
                with tr.span(
                    "crag.evaluate",
                    input={"docs": len(result), "question": question},
                ) as sp:
                    sp.output({"confidence": confidence, "route": route})

                if route != "correct":
                    rewritten = self._rewriter.rewrite(question)
                    if not rewritten or rewritten.strip() == question.strip():
                        rewritten = f"{question.strip()} SQL dialect migration compatibility".strip()
                    crag_trace["rewritten_query"] = rewritten
                    with tr.span("crag.rewrite", input={"question": question}) as sp:
                        sp.output({"rewritten_query": rewritten})
                    rewritten_trace = {
                        "channels": [],
                        "degraded_channels": trace["degraded_channels"],
                        "graph": trace["graph"],
                    }
                    rewritten_items = self._retrieve_once(
                        rewritten,
                        coarse_k,
                        filters,
                        internal_mode,
                        name,
                        state,
                        tr,
                        rewritten_trace,
                    )
                    result = self._merge_corrective_results(
                        question, result, rewritten_items, coarse_k
                    )
                    for channel in rewritten_trace["channels"]:
                        if channel not in trace["channels"]:
                            trace["channels"].append(channel)
                trace["crag"] = crag_trace

            result = result[:top_k]
            trace["result_ids"] = [item["id"] for item in result]
            if parent_trace is None:
                tr.output(trace)
        if trace_out is not None:
            trace_out.update(trace)
        return result

    def _retrieve_once(
        self,
        question: str,
        top_n: int,
        filters: Optional[Dict[str, Any]],
        mode: str,
        collection: str,
        state: Dict[str, Any],
        tr: Any,
        trace: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        use_bm25 = mode in {"bm25", "hybrid", "rerank", "crag", "full"}
        use_dense = mode in {"dense", "dense_rerank", "hybrid", "rerank", "crag", "full"}
        use_sparse = mode in {"hybrid", "rerank", "crag", "full"}
        use_rerank = mode in {"dense_rerank", "rerank", "crag", "full"}
        use_graph = mode == "full"

        ranked: List[Tuple[str, List[Tuple[str, float]]]] = []
        if use_bm25 and state["bm25"] is not None:
            with tr.span("bm25.search", input={"top_n": top_n}) as sp:
                scores = state["bm25"].get_scores(_tokenize(question))
                pairs = sorted(
                    zip((doc["id"] for doc in state["docs"]), scores),
                    key=lambda pair: float(pair[1]),
                    reverse=True,
                )
                bm25_hits = [
                    (doc_id, float(score))
                    for doc_id, score in pairs
                    if _matches_filters(state["by_id"][doc_id], filters)
                ][:top_n]
                ranked.append(("bm25", bm25_hits))
                sp.output({"hits": len(bm25_hits)})

        dense_ready = self._dense_available()
        if use_dense and dense_ready:
            try:
                with tr.span("bge.encode_query", input={"query_len": len(question)}) as sp:
                    vectors = self._embedder.encode_full([question])
                    dense = vectors["dense_vecs"][0]
                    sparse_raw = vectors["lexical_weights"][0] or {}
                    sparse = {int(k): float(v) for k, v in sparse_raw.items()}
                    sp.output({"dense_dim": len(dense), "sparse_terms": len(sparse)})
                dense_rows = self._qdrant.search_dense(
                    collection, dense, k=top_n, filters=filters
                )
                dense_hits = self._known_filtered_hits(dense_rows, state, filters, top_n)
                ranked.append(("dense", dense_hits))
                if use_sparse:
                    if sparse:
                        sparse_rows = self._qdrant.search_sparse(
                            collection, sparse, k=top_n, filters=filters
                        )
                        sparse_hits = self._known_filtered_hits(
                            sparse_rows, state, filters, top_n
                        )
                        ranked.append(("sparse", sparse_hits))
                    else:
                        self._degrade(trace, "sparse:no_lexical_weights")
            except Exception as exc:  # noqa: BLE001
                log.warning("[HybridRetriever] vector channels failed: %s", exc)
                self._degrade(trace, "dense:runtime_error")
                if use_sparse:
                    self._degrade(trace, "sparse:runtime_error")
        elif use_dense:
            self._degrade(trace, "dense:unavailable")
            if use_sparse:
                self._degrade(trace, "sparse:unavailable")

        if use_graph:
            graph_hits = self._graph_ranked(question, collection, state, filters, top_n)
            trace.setdefault("graph", {})["hits"] = len(graph_hits)
            if graph_hits:
                ranked.append(("graph", graph_hits))
            else:
                self._degrade(trace, "graph:no_hits")

        ranked = [(name, rows) for name, rows in ranked if rows]
        if not ranked and state["bm25"] is not None:
            # Compatibility aliases degrade loudly to BM25 instead of returning
            # a misleading empty response in a lightweight installation.
            self._degrade(trace, "fallback:bm25")
            scores = state["bm25"].get_scores(_tokenize(question))
            rows = sorted(
                zip((doc["id"] for doc in state["docs"]), scores),
                key=lambda pair: float(pair[1]),
                reverse=True,
            )
            ranked = [("bm25_fallback", [
                (doc_id, float(score))
                for doc_id, score in rows
                if _matches_filters(state["by_id"][doc_id], filters)
            ][:top_n])]
        if not ranked:
            return []

        for channel, _ in ranked:
            if channel not in trace["channels"]:
                trace["channels"].append(channel)
        fused = self._fuse_channels(ranked, top_n)
        candidates = self._materialize(fused, state)
        if use_rerank:
            if self._rerank_available():
                candidates = self._apply_rerank(question, candidates, top_n)
                trace["reranked"] = True
            else:
                self._degrade(trace, "rerank:unavailable")
                trace["reranked"] = False
        return candidates[:top_n]

    def _fuse_channels(
        self,
        ranked: List[Tuple[str, List[Tuple[str, float]]]],
        top_n: int,
    ) -> List[Tuple[str, float, Dict[str, float]]]:
        if len(ranked) == 1:
            name, rows = ranked[0]
            return [(doc_id, score, {name: float(rank)}) for rank, (doc_id, score) in enumerate(rows, 1)]
        weight_values = self._rrf_weights()
        weights_by_name = {
            "bm25": weight_values[0],
            "dense": weight_values[1],
            "sparse": weight_values[2],
            "graph": weight_values[3],
            "bm25_fallback": 1.0,
        }
        rows = [items for _, items in ranked]
        weights = [weights_by_name.get(name, 1.0) for name, _ in ranked]
        fused = rrf_merge(rows, k=settings.rrf_k, top_n=top_n, weights=weights)
        translated: List[Tuple[str, float, Dict[str, float]]] = []
        channel_names = [name for name, _ in ranked]
        for doc_id, score, channel_ranks in fused:
            translated.append((
                doc_id,
                float(score),
                {channel_names[int(index)]: rank for index, rank in channel_ranks.items()},
            ))
        return translated

    @staticmethod
    def _materialize(
        fused: List[Tuple[str, float, Dict[str, float]]],
        state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for doc_id, score, channels in fused:
            doc = state["by_id"].get(doc_id)
            if doc is None:
                continue
            result.append({
                "id": doc_id,
                "text": doc["text"],
                "score": float(score),
                "rrf_score": float(score),
                "channels": channels,
                "source": doc.get("source", "unknown"),
                "meta": doc.get("meta") or {},
            })
        return result

    def _apply_rerank(
        self, question: str, candidates: List[Dict[str, Any]], top_n: int
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        ranking = self._reranker.rerank(
            question, [item["text"] for item in candidates], top_n=top_n
        )
        result: List[Dict[str, Any]] = []
        for index, score in ranking:
            item = dict(candidates[index])
            item["rerank_score"] = float(score)
            item["score"] = float(score)
            result.append(item)
        return result

    def _merge_corrective_results(
        self,
        question: str,
        initial: List[Dict[str, Any]],
        rewritten: List[Dict[str, Any]],
        top_n: int,
    ) -> List[Dict[str, Any]]:
        if not rewritten:
            return initial
        sources = {item["id"]: item for item in [*initial, *rewritten]}
        fused = rrf_merge(
            [
                [(item["id"], item["score"]) for item in initial],
                [(item["id"], item["score"]) for item in rewritten],
            ],
            k=settings.rrf_k,
            top_n=top_n,
            weights=[1.0, 1.0],
        )
        merged: List[Dict[str, Any]] = []
        for doc_id, score, ranks in fused:
            item = dict(sources[doc_id])
            item["score"] = float(score)
            item["rrf_score"] = float(score)
            item["channels"] = {
                **(item.get("channels") or {}),
                **({"crag_initial": ranks["0"]} if "0" in ranks else {}),
                **({"crag_rewrite": ranks["1"]} if "1" in ranks else {}),
            }
            merged.append(item)
        if self._rerank_available():
            return self._apply_rerank(question, merged, top_n)
        return merged

    @staticmethod
    def _known_filtered_hits(
        rows: List[Tuple[str, float, Dict[str, Any]]],
        state: Dict[str, Any],
        filters: Optional[Dict[str, Any]],
        top_n: int,
    ) -> List[Tuple[str, float]]:
        result: List[Tuple[str, float]] = []
        for doc_id, score, _payload in rows:
            doc = state["by_id"].get(doc_id)
            if doc is not None and _matches_filters(doc, filters):
                result.append((doc_id, float(score)))
            if len(result) >= top_n:
                break
        return result

    def _graph_ranked(
        self,
        question: str,
        collection: str,
        state: Dict[str, Any],
        filters: Optional[Dict[str, Any]],
        top_n: int,
    ) -> List[Tuple[str, float]]:
        index = self._graph_for(collection, state)
        if index is None or not getattr(index, "nodes", None):
            return []
        try:
            result = index.query_local(
                question, max_entities=max(3, top_n), hop=1, weight_threshold=0.2
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("[HybridRetriever] graph query failed: %s", exc)
            return []
        ids: List[Tuple[str, float]] = []
        for rank, doc_id in enumerate(result.get("hits") or [], 1):
            ids.append((str(doc_id), 1.0 / rank))
        for rank, node in enumerate(result.get("neighbors") or [], 1):
            doc_id = str(node.get("id") or "")
            ids.append((doc_id, float(node.get("_edge_weight") or 0.1) / rank))
        seen = set()
        filtered: List[Tuple[str, float]] = []
        for doc_id, score in ids:
            if doc_id in seen:
                continue
            doc = state["by_id"].get(doc_id)
            if doc is None or not _matches_filters(doc, filters):
                continue
            seen.add(doc_id)
            filtered.append((doc_id, score))
            if len(filtered) >= top_n:
                break
        return filtered

    def _graph_for(self, collection: str, state: Dict[str, Any]) -> Any:
        if collection == self.collection and self.graph_index is not None:
            return self.graph_index
        cached = self._graph_indexes.get(collection)
        if cached is not None:
            return cached
        try:
            from app.graphs.graphrag import GraphRagIndex
            from app.graphs.kb_graph_builder import build_graph_from_docs

            index = GraphRagIndex(max_community_size=20)
            graph = build_graph_from_docs(state["docs"])
            index.build(graph["nodes"], graph["edges"])
            self._graph_indexes[collection] = index
            return index
        except Exception as exc:  # noqa: BLE001
            log.warning("[HybridRetriever] graph build failed collection=%s: %s", collection, exc)
            return None

    def capabilities(self, collection: Optional[str] = None) -> Dict[str, Any]:
        name = validate_collection_name(collection or self.collection)
        state = self._state(name)
        graph = self._graph_for(name, state) if state and state["docs"] else None
        return {
            "collection": name,
            "collections": sorted(self._collections),
            "bm25": bool(state and state["bm25"] is not None),
            "dense": self._dense_available(),
            "sparse": self._dense_available(),
            "rerank": self._rerank_available(),
            "graphrag": bool(graph and getattr(graph, "nodes", None)),
            "modes": ["bm25", "hybrid", "rerank", "crag", "full"],
            "legacy_mode_aliases": {"vector": "dense", "vector_rerank": "dense_rerank"},
            "qdrant_url": settings.qdrant_url if self._qdrant and self._qdrant.available else None,
            "embed_model": settings.bge_model if self._embedder and self._embedder.available else None,
            "rerank_model": settings.reranker_model if self._reranker and self._reranker.available else None,
            "rrf_k": settings.rrf_k,
            "docs": len(state["docs"]) if state else 0,
            "chunk_strategy_default": settings.chunk_strategy,
        }

    def _maybe_seed_qdrant(self, collection: str) -> None:
        state = self._state(collection)
        if not state or not state["docs"] or not self._dense_available():
            return
        try:
            client = self._qdrant._get_client()
            try:
                count = client.count(collection_name=collection).count
                if count is not None and count >= len(state["docs"]):
                    return
            except Exception:  # noqa: BLE001
                pass
            self._index_qdrant(state["docs"], collection)
        except Exception as exc:  # noqa: BLE001
            log.warning("[HybridRetriever] Qdrant seed failed collection=%s: %s", collection, exc)

    def _index_qdrant(self, docs: List[Dict[str, Any]], collection: str) -> None:
        if not docs or not self._dense_available():
            return
        with_embedding = [doc for doc in docs if isinstance(doc.get("embedding"), list) and doc["embedding"]]
        needs_embedding = [doc for doc in docs if doc not in with_embedding]
        if with_embedding:
            self._qdrant.upsert(
                collection,
                ids=[doc["id"] for doc in with_embedding],
                texts=[doc["text"] for doc in with_embedding],
                dense_vecs=[doc["embedding"] for doc in with_embedding],
                sparse_dicts=[{} for _ in with_embedding],
                metas=[doc.get("meta") or {} for doc in with_embedding],
            )
        if needs_embedding:
            encoded = self._embedder.encode_full([doc["text"] for doc in needs_embedding])
            sparse = [
                {int(key): float(value) for key, value in (weights or {}).items()}
                for weights in encoded["lexical_weights"]
            ]
            self._qdrant.upsert(
                collection,
                ids=[doc["id"] for doc in needs_embedding],
                texts=[doc["text"] for doc in needs_embedding],
                dense_vecs=encoded["dense_vecs"],
                sparse_dicts=sparse,
                metas=[doc.get("meta") or {} for doc in needs_embedding],
            )

    def _dense_available(self) -> bool:
        return bool(
            self._embedder
            and self._embedder.available
            and self._qdrant
            and self._qdrant.available
        )

    def _rerank_available(self) -> bool:
        return bool(self._reranker and self._reranker.available)

    @staticmethod
    def _degrade(trace: Dict[str, Any], reason: str) -> None:
        degraded = trace.setdefault("degraded_channels", [])
        if reason not in degraded:
            degraded.append(reason)

    @staticmethod
    def _rrf_weights() -> List[float]:
        try:
            values = [float(value.strip()) for value in settings.rrf_channel_weights.split(",")]
        except ValueError:
            values = []
        return (values + [1.0, 1.0, 1.0, 1.0])[:4]
