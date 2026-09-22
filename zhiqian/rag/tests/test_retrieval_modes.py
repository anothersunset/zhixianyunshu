"""Deterministic regression tests for retrieval mode semantics."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.pipelines.retriever import HybridRetriever


DOCS = [
    {
        "id": "bm25-doc",
        "text": "MySQL IFNULL maps to PostgreSQL COALESCE for null handling",
        "source": "kb/null",
        "meta": {"source_dialect": "mysql", "target_dialect": "postgres"},
    },
    {
        "id": "dense-doc",
        "text": "GROUP_CONCAT becomes STRING_AGG during SQL migration",
        "source": "kb/aggregate",
        "meta": {"source_dialect": "mysql", "target_dialect": "postgres"},
    },
    {
        "id": "graph-doc",
        "text": "AUTO_INCREMENT uses identity or sequence semantics",
        "source": "kb/identity",
        "meta": {"source_dialect": "oracle", "target_dialect": "postgres"},
    },
]


class FakeEmbedder:
    available = True

    def encode_full(self, texts):
        return {
            "dense_vecs": [[float(len(text))] for text in texts],
            "lexical_weights": [{1: 1.0, 2: 0.5} for _ in texts],
            "colbert_vecs": [[] for _ in texts],
        }


class FakeQdrant:
    available = True

    def __init__(self):
        self.calls = []

    def _get_client(self):
        return SimpleNamespace(count=lambda **_kwargs: SimpleNamespace(count=len(DOCS)))

    def upsert(self, *_args, **_kwargs):
        return True

    def search_dense(self, collection, _dense, k=50, filters=None):
        self.calls.append(("dense", collection, filters))
        return [
            ("dense-doc", 0.95, {}),
            ("graph-doc", 0.8, {}),
            ("bm25-doc", 0.7, {}),
        ][:k]

    def search_sparse(self, collection, _sparse, k=50, filters=None):
        self.calls.append(("sparse", collection, filters))
        return [
            ("bm25-doc", 0.9, {}),
            ("dense-doc", 0.75, {}),
            ("graph-doc", 0.6, {}),
        ][:k]


class BrokenDenseQdrant(FakeQdrant):
    """dense 查询运行时抛异常, sparse 正常 — 模拟 Qdrant 半路挂掉。"""

    def search_dense(self, collection, _dense, k=50, filters=None):
        self.calls.append(("dense", collection, filters))
        raise RuntimeError("qdrant connection refused")


class BrokenVectorQdrant(FakeQdrant):
    """dense + sparse 全部运行时抛异常。"""

    def search_dense(self, collection, _dense, k=50, filters=None):
        self.calls.append(("dense", collection, filters))
        raise RuntimeError("qdrant connection refused")

    def search_sparse(self, collection, _sparse, k=50, filters=None):
        self.calls.append(("sparse", collection, filters))
        raise RuntimeError("qdrant connection refused")


class FakeReranker:
    available = True

    def rerank(self, _query, candidates, top_n=5):
        return [(index, 1.0 - index * 0.1) for index in range(min(len(candidates), top_n))]


class AmbiguousEvaluator:
    def score(self, _question, _docs):
        return 0.3

    def route(self, _confidence):
        return "ambiguous"


class FakeGraph:
    nodes = {"graph-doc": object()}

    def query_local(self, *_args, **_kwargs):
        return {"hits": ["graph-doc"], "neighbors": []}


@pytest.fixture()
def retriever():
    value = HybridRetriever(
        docs=DOCS,
        embedder=FakeEmbedder(),
        qdrant=FakeQdrant(),
        reranker=FakeReranker(),
        evaluator=AmbiguousEvaluator(),
    )
    value.graph_index = FakeGraph()
    return value


@pytest.mark.parametrize(
    ("mode", "required_channels", "reranked"),
    [
        ("bm25", {"bm25"}, False),
        ("hybrid", {"bm25", "dense", "sparse"}, False),
        ("rerank", {"bm25", "dense", "sparse"}, True),
    ],
)
def test_base_modes_have_distinct_channel_semantics(retriever, mode, required_channels, reranked):
    trace = {}
    results = retriever.search("IFNULL migration", mode=mode, top_k=3, trace_out=trace)

    assert results
    assert set(trace["channels"]) == required_channels
    assert bool(trace.get("reranked")) is reranked
    assert trace["crag"] is None


def test_crag_evaluates_and_rewrites_low_confidence_query(retriever):
    trace = {}
    results = retriever.search("IFNULL migration", mode="crag", top_k=3, trace_out=trace)

    assert results
    assert trace["crag"]["evaluated"] is True
    assert trace["crag"]["route"] == "ambiguous"
    assert trace["crag"]["rewritten_query"] != "IFNULL migration"
    assert any("crag_rewrite" in item["channels"] for item in results)


def test_full_fuses_graph_evidence(retriever):
    trace = {}
    results = retriever.search("identity sequence", mode="full", top_k=3, trace_out=trace)

    assert results
    assert "graph" in trace["channels"]
    assert trace["graph"] == {"attempted": True, "hits": 1}
    graph_item = next(item for item in results if item["id"] == "graph-doc")
    assert "graph" in graph_item["channels"]


def test_collection_isolation_and_qdrant_filter_pushdown(retriever):
    inserted = retriever.add(
        [{
            "id": "tenant-b-only",
            "text": "Oracle NVL migration",
            "source": "tenant-b",
            "meta": {"source_dialect": "oracle", "target_dialect": "postgres"},
        }],
        collection="tenant-b",
    )
    assert inserted == 1

    tenant_results = retriever.search(
        "Oracle NVL", collection="tenant-b", mode="bm25", top_k=5
    )
    default_results = retriever.search(
        "Oracle NVL", collection="zhiqian-default", mode="bm25", top_k=5
    )
    assert [item["id"] for item in tenant_results] == ["tenant-b-only"]
    assert "tenant-b-only" not in {item["id"] for item in default_results}

    filters = {"source_dialect": "mysql", "target_dialect": "postgres"}
    filtered = retriever.search(
        "migration", mode="hybrid", filters=filters, top_k=5
    )
    assert filtered
    assert all(item["meta"]["source_dialect"] == "mysql" for item in filtered)
    vector_calls = [call for call in retriever._qdrant.calls if call[0] in {"dense", "sparse"}]
    assert vector_calls
    assert all(call[2] == filters for call in vector_calls)


def test_legacy_mode_names_remain_available_for_one_release(retriever):
    vector_trace = {}
    rerank_trace = {}
    assert retriever.search("migration", mode="vector", trace_out=vector_trace)
    assert retriever.search("migration", mode="vector_rerank", trace_out=rerank_trace)
    assert vector_trace["effective_mode"] == "dense"
    assert rerank_trace["effective_mode"] == "dense_rerank"
    assert vector_trace["channels"] == ["dense"]
    assert rerank_trace["reranked"] is True


def test_dense_runtime_error_visible_in_trace_and_bm25_survives():
    """Qdrant dense 半路挂掉: trace 必须记录 dense:runtime_error, bm25/sparse 照常出结果。"""
    retriever = HybridRetriever(
        docs=DOCS,
        embedder=FakeEmbedder(),
        qdrant=BrokenDenseQdrant(),
        reranker=FakeReranker(),
        evaluator=AmbiguousEvaluator(),
    )
    trace = {}
    results = retriever.search("IFNULL migration", mode="hybrid", top_k=3, trace_out=trace)

    assert results, "bm25 通道必须继续返回结果"
    assert "bm25" in trace["channels"]
    assert "sparse" in trace["channels"], "sparse 通道不受 dense 故障拖累"
    assert "dense:runtime_error" in trace["degraded_channels"]
    assert "sparse:runtime_error" not in trace["degraded_channels"]


def test_all_vector_channels_runtime_error_visible_in_trace():
    """dense+sparse 同时挂: 两条 runtime_error 都进 trace, bm25 兜底仍返回。"""
    retriever = HybridRetriever(
        docs=DOCS,
        embedder=FakeEmbedder(),
        qdrant=BrokenVectorQdrant(),
        reranker=FakeReranker(),
        evaluator=AmbiguousEvaluator(),
    )
    trace = {}
    results = retriever.search("IFNULL migration", mode="hybrid", top_k=3, trace_out=trace)

    assert results, "bm25 兜底必须返回结果"
    assert "bm25" in trace["channels"]
    assert "dense:runtime_error" in trace["degraded_channels"]
    assert "sparse:runtime_error" in trace["degraded_channels"]
