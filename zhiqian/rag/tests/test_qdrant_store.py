"""Qdrant store 语义回归:
- 运行时检索失败必须抛 QdrantSearchError (绝不吞成空列表静默降级);
- import-probe 的 available=False 语义保持兼容 (返回空列表, 不抛异常)。
"""
from __future__ import annotations

import sys
import types

import pytest

from app.store.qdrant_store import QdrantSearchError, QdrantStore


@pytest.fixture
def fake_qdrant_modules(monkeypatch):
    """qdrant-client 未安装的环境里, 注入假模块让 store 走到运行时路径。"""
    qdrant_client = types.ModuleType("qdrant_client")
    http = types.ModuleType("qdrant_client.http")
    models = types.ModuleType("qdrant_client.http.models")
    qdrant_client.http = http
    http.models = models
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant_client)
    monkeypatch.setitem(sys.modules, "qdrant_client.http", http)
    monkeypatch.setitem(sys.modules, "qdrant_client.http.models", models)


class _ExplodingClient:
    def query_points(self, **_kwargs):
        raise ConnectionError("qdrant server went down mid-flight")


def _runtime_ready_store() -> QdrantStore:
    """绕过 import 探针, 直接处于 '已启用但服务端运行时不可达' 状态。"""
    store = QdrantStore(url="http://localhost:6333")
    store._available = True  # 模拟 import 探针通过 (qdrant-client 已安装)
    store._client = _ExplodingClient()
    return store


def test_search_dense_raises_qdrant_search_error_on_runtime_failure():
    store = _runtime_ready_store()
    with pytest.raises(QdrantSearchError):
        store.search_dense("col", [0.1, 0.2], k=3)


def test_search_sparse_raises_qdrant_search_error_on_runtime_failure():
    store = _runtime_ready_store()
    with pytest.raises(QdrantSearchError):
        store.search_sparse("col", {1: 1.0, 2: 0.5}, k=3)


def test_runtime_error_chains_original_exception(fake_qdrant_modules):
    store = _runtime_ready_store()
    try:
        store.search_dense("col", [0.1], k=1)
    except QdrantSearchError as exc:
        assert isinstance(exc.__cause__, ConnectionError)
    else:  # pragma: no cover
        pytest.fail("search_dense 应抛 QdrantSearchError")


def test_unavailable_store_keeps_legacy_empty_list_semantics():
    """available=False (依赖未装/未启用) 仍返回空列表, 不抛异常 — 保持兼容。"""
    store = QdrantStore()
    if store.available:
        pytest.skip("qdrant-client 已安装, 无法验证 import-probe 关闭路径")
    assert store.available is False
    assert store.search_dense("col", [0.1], k=3) == []
    assert store.search_sparse("col", {1: 1.0}, k=3) == []
