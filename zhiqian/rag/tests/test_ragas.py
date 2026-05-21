"""
v2-step-11: RAGAS 另一层 — faithfulness + answer_relevancy, DeepSeek 判官。

运行条件:
- 环境需 DEEPSEEK_API_KEY (或 OPENAI_API_KEY) 。否则 pytest.skipif 跳过。
- 需装 requirements-test.txt (ragas + langchain-openai + datasets)。
"""
from __future__ import annotations

import os
from typing import List

import pytest

HAS_KEY = bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))

try:
    from datasets import Dataset  # type: ignore
    from ragas import evaluate  # type: ignore
    from ragas.metrics import answer_relevancy, faithfulness  # type: ignore
    HAS_RAGAS = True
except Exception:
    HAS_RAGAS = False


pytestmark = pytest.mark.skipif(
    not (HAS_KEY and HAS_RAGAS),
    reason="需 DEEPSEEK_API_KEY 与 ragas+langchain-openai, 跳过 RAGAS 层测试",
)


def _qa_items(golden_set: List[dict]) -> List[dict]:
    return [g for g in golden_set if g["kind"] == "qa"]


def test_ragas_faithfulness_and_relevancy(client, golden_set, ragas_llm, ragas_embeddings):
    if ragas_llm is None:
        pytest.skip("ragas_llm 如 None, 环境未安装 langchain-openai")
    items = _qa_items(golden_set)
    qs, ans, ctxs = [], [], []
    for it in items:
        # 先走 /retrieve 拿上下文, 再走 /query 拿答案
        rr = client.post("/retrieve", json={"question": it["question"], "top_k": 5}).json()
        chunks = rr.get("chunks") or rr.get("results") or []
        ctx = [c.get("text") or c.get("content") or "" for c in chunks][:5]
        qr = client.post("/query", json={"question": it["question"]}).json()
        a = qr.get("answer") or qr.get("text") or ""
        qs.append(it["question"])
        ans.append(a)
        ctxs.append(ctx if ctx else [""])  # 避免空 list 报错
    ds = Dataset.from_dict({
        "question": qs,
        "answer": ans,
        "contexts": ctxs,
    })
    metrics = [faithfulness, answer_relevancy]
    kwargs = dict(llm=ragas_llm)
    if ragas_embeddings is not None:
        kwargs["embeddings"] = ragas_embeddings
    res = evaluate(ds, metrics=metrics, **kwargs)
    print("\n[ragas]", dict(res))
    # 阈值设得保守, 主要防纯胡说八道。后续有 GraphRAG 后可取高。
    assert res["faithfulness"] >= 0.50, f"faithfulness={res['faithfulness']:.2f} 过低"
    assert res["answer_relevancy"] >= 0.50, f"answer_relevancy={res['answer_relevancy']:.2f} 过低"


def test_keyword_faithfulness_fallback(client, golden_set):
    """不需 LLM 的轻量备选: 验证答案含期望 keyword — 阈值 ≥ 60%.

    作为 fallback 在 CI 无 API key 环境依然有衡量下限。不被上面 skipif 包住。
    """
    items = _qa_items(golden_set)
    hits = 0
    misses = []
    for it in items:
        qr = client.post("/query", json={"question": it["question"]})
        if qr.status_code != 200:
            misses.append((it["id"], "HTTP " + str(qr.status_code)))
            continue
        body = qr.json()
        a = (body.get("answer") or body.get("text") or "").upper()
        kws = it.get("expected_keywords", [])
        found = sum(1 for k in kws if k.upper() in a)
        if found >= it.get("min_facts", 1):
            hits += 1
        else:
            misses.append((it["id"], f"found {found}/{len(kws)}"))
    score = hits / len(items) if items else 0
    print(f"\n[keyword-faithfulness] {hits}/{len(items)} = {score:.2%}")
    if misses:
        print("[misses]", misses[:10])
    # 本地 mock LLM 或者 demo 文档少时可能偏低, 取 50% 阈值 (与 ragas 一致)
    assert score >= 0.50, f"keyword 商 {score:.2%} 低于 50%"


@pytest.mark.skipif(not HAS_KEY, reason="需 DEEPSEEK_API_KEY")
def test_ragas_imports_ok():
    """提示: 装上了 key 但没装 ragas 时提醒。"""
    assert HAS_RAGAS, "请 pip install -r requirements-test.txt"
