"""
v2-step-11: 检索层测试。

衡量指标:
- recall@5: 黄金集 6 条 retrieve, 期望 doc 在返回 top-5 里出现的比例 ≥ 0.80
- p50 响应时间 < 1s (单进程内存检索, 不拉 BGE/Qdrant 交互, 走 fallback Jaccard)
不调 LLM, 不调外部服务, ~ 几秒跑完。
"""
from __future__ import annotations

import statistics
import time
from typing import List

import pytest


def _retrieve_items(golden_set: List[dict]) -> List[dict]:
    return [g for g in golden_set if g["kind"] == "retrieve"]


def test_retrieve_items_present(golden_set):
    items = _retrieve_items(golden_set)
    assert len(items) >= 6, f"需 ≥ 6 条 retrieve case, 现 {len(items)}"


def test_retriever_recall_at_5(client, golden_set):
    items = _retrieve_items(golden_set)
    hits = 0
    timings = []
    failures = []
    for it in items:
        t0 = time.time()
        resp = client.post("/retrieve", json={"question": it["question"], "top_k": it.get("top_k", 5)})
        timings.append(time.time() - t0)
        if resp.status_code != 200:
            failures.append((it["id"], "HTTP " + str(resp.status_code)))
            continue
        body = resp.json()
        # 兼容两种返回格式: {chunks:[{doc_id}]} 或 {results:[{id}]}
        docs = []
        for arr_key in ("chunks", "results", "hits", "items"):
            if arr_key in body and isinstance(body[arr_key], list):
                docs = body[arr_key]
                break
        ids = [d.get("doc_id") or d.get("id") or "" for d in docs]
        expected = set(it["expected_doc_ids"])
        if expected & set(ids):
            hits += 1
        else:
            failures.append((it["id"], "top5=" + ",".join(ids[:5])))
    recall = hits / len(items)
    p50 = statistics.median(timings) if timings else 0
    print(f"\n[recall@5] hits={hits}/{len(items)} = {recall:.2%}, p50={p50*1000:.0f}ms")
    if failures:
        print("[failures]", failures)
    assert recall >= 0.80, f"recall@5={recall:.2%} 低于阈值 80%"
    assert p50 < 1.0, f"p50={p50*1000:.0f}ms 超过 1s"


def test_retriever_returns_non_empty(client, golden_set):
    """基本联调: /retrieve 不该返回空列表。"""
    items = _retrieve_items(golden_set)
    empties = 0
    for it in items:
        resp = client.post("/retrieve", json={"question": it["question"], "top_k": 5})
        if resp.status_code != 200:
            empties += 1
            continue
        body = resp.json()
        docs = body.get("chunks") or body.get("results") or []
        if not docs:
            empties += 1
    assert empties == 0, f"{empties}/{len(items)} 条 查询返回空结果"
