"""migration_client 的 mock 双守卫自检（离线，不发任何网络请求）。

守卫语义（见 migration_client.run_migration）：
1. LLM 守卫：响应 raw.real is False（后端在用 mock LLM 输出）且未设
   ZHIQIAN_ALLOW_MOCK_EVAL → RuntimeError 中止，宁可不跑也不产出假数据。
2. 检索守卫：响应 raw.retrieval_real is False（检索降级到后端 mock）且未设
   ZHIQIAN_ALLOW_MOCK_RETRIEVAL → RuntimeError 中止，防止消融梯度被污染。

环境变量在 MigrationClient.__init__ 里读取，因此先 monkeypatch 环境再构造
客户端；HTTP 层用假 Session 替换，只验证守卫逻辑本身。
"""
from __future__ import annotations

from datetime import timedelta

import pytest

import eval.migration_client as mc


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.elapsed = timedelta(seconds=0.01)

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    """替代 requests.Session：返回预置 payload，记录请求参数，不联网。"""

    def __init__(self, payload):
        self._payload = payload
        self.last_request = None

    def post(self, url, json=None, timeout=None):
        self.last_request = {"url": url, "json": json, "timeout": timeout}
        return _FakeResponse(self._payload)


def _make_client(monkeypatch, payload, **env):
    # 先清掉宿主环境可能残留的两个开关，保证"未允许"是确定的初始态
    for var in ("ZHIQIAN_ALLOW_MOCK_EVAL", "ZHIQIAN_ALLOW_MOCK_RETRIEVAL"):
        monkeypatch.delenv(var, raising=False)
    for var, value in env.items():
        monkeypatch.setenv(var, value)
    client = mc.MigrationClient(cooldown=0)  # cooldown=0：节流不 sleep
    client.session = _FakeSession(payload)
    return client


def _run(client, retrieval="bm25"):
    return client.run_migration(
        source_sql="SELECT IFNULL(x, 0) FROM t",
        pair="mysql_opengauss",
        retrieval=retrieval,
        fast=True,
    )


# ── LLM mock 守卫 ──

def test_mock_llm_response_aborts_when_not_allowed(monkeypatch):
    client = _make_client(monkeypatch, {"target_sql": "SELECT 1", "raw": {"real": False}})
    with pytest.raises(RuntimeError, match="mock LLM"):
        _run(client)


def test_mock_llm_response_passes_with_allow_mock_eval(monkeypatch):
    client = _make_client(
        monkeypatch, {"target_sql": "SELECT 1", "raw": {"real": False}},
        ZHIQIAN_ALLOW_MOCK_EVAL="1",
    )
    result = _run(client)
    assert result.target_sql == "SELECT 1"
    # 后端未上报 retrieval_real 时保持 None（区分"未上报"与"确认真实"）
    assert result.retrieval_real is None


def test_allow_mock_eval_accepts_yes_not_just_one(monkeypatch):
    client = _make_client(
        monkeypatch, {"raw": {"real": False}},
        ZHIQIAN_ALLOW_MOCK_EVAL="YES",
    )
    result = _run(client)
    assert result.retrieval_real is None


def test_allow_mock_eval_zero_still_blocks(monkeypatch):
    client = _make_client(
        monkeypatch, {"raw": {"real": False}},
        ZHIQIAN_ALLOW_MOCK_EVAL="0",
    )
    with pytest.raises(RuntimeError, match="mock LLM"):
        _run(client)


# ── 检索 mock 守卫 ──

def test_mock_retrieval_aborts_when_not_allowed(monkeypatch):
    client = _make_client(monkeypatch, {"raw": {"retrieval_real": False}})
    with pytest.raises(RuntimeError, match="Retrieval fell back"):
        _run(client, retrieval="vector_rerank")


def test_mock_retrieval_passes_with_allow_mock_retrieval(monkeypatch):
    client = _make_client(
        monkeypatch, {"raw": {"retrieval_real": False}},
        ZHIQIAN_ALLOW_MOCK_RETRIEVAL="1",
    )
    result = _run(client)
    # 放行但如实记录检索是 mock 的
    assert result.retrieval_real is False


# ── 守卫顺序与正常路径 ──

def test_llm_guard_fires_before_retrieval_guard(monkeypatch):
    """两个守卫同时触发时，LLM 守卫（先检查）的报错信息优先。"""
    client = _make_client(monkeypatch, {"raw": {"real": False, "retrieval_real": False}})
    with pytest.raises(RuntimeError, match="mock LLM"):
        _run(client)


def test_both_allows_let_double_mock_response_through(monkeypatch):
    client = _make_client(
        monkeypatch, {"raw": {"real": False, "retrieval_real": False}},
        ZHIQIAN_ALLOW_MOCK_EVAL="true",
        ZHIQIAN_ALLOW_MOCK_RETRIEVAL="true",
    )
    result = _run(client)
    assert result.retrieval_real is False


def test_real_response_returns_result_with_fields_intact(monkeypatch):
    payload = {
        "target_sql": "SELECT COALESCE(x, 0) FROM t",
        "report_points": ["p1", "p2"],
        "risk_level": "low",
        "retrieved_ids": ["kb-001", "kb-002"],
        "raw": {"real": True, "retrieval_real": True},
    }
    client = _make_client(monkeypatch, payload)
    result = _run(client, retrieval="full")
    assert result.target_sql == payload["target_sql"]
    assert result.report_points == ["p1", "p2"]
    assert result.risk_level == "low"
    assert result.retrieved_ids == ["kb-001", "kb-002"]
    assert result.retrieval_real is True
    assert result.raw is payload
    # 请求确实发到了 /migrate 端点且带上了消融参数
    req = client.session.last_request
    assert req["url"].endswith("/migrate")
    assert req["json"]["retrieval"] == "full"
    assert req["json"]["pair"] == "mysql_opengauss"
