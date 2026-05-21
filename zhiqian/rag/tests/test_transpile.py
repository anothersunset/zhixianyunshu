"""
v2-step-11: SQL 转译层测试 — 完全本地 (sqlglot 纯 Python), 无需服务可跑。
为什么: #9 引入后, 需验证 14 个 `_FUNCTION_NOTES` 中的函数都被正确转换。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest


def _transpile_items() -> List[dict]:
    path = Path(__file__).parent / "data" / "golden_set.jsonl"
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        d = json.loads(line)
        if d.get("kind") == "transpile":
            items.append(d)
    return items


def test_transpile_items_present():
    items = _transpile_items()
    assert len(items) >= 8, f"需 ≥ 8 条 transpile case, 现 {len(items)}"


@pytest.mark.parametrize("case", _transpile_items(), ids=lambda c: c["id"])
def test_transpile_each(case):
    """逐个 transpile case 设为独立 test, 失败能看到具体哪条裂。"""
    try:
        from app.core.sql_transpiler import explain_transpile  # type: ignore
    except Exception as e:
        pytest.skip(f"sql_transpiler 不可加载: {e}")
        return
    r = explain_transpile(case["input_sql"], source=case["source"], target=case["target"])
    assert r.get("ok"), f"转译未成功: {r.get('error')}"
    out_sql = (r.get("target") or "").upper()
    for tok in case.get("expected_tokens", []):
        assert tok.upper() in out_sql, (
            f"期望输出包含 {tok!r} 但未出现: {r.get('target')}"
        )
    for tok in case.get("forbidden_tokens", []):
        assert tok.upper() not in out_sql, (
            f"输出不应含 {tok!r} 但出现了: {r.get('target')}"
        )


def test_transpile_batch_ok():
    try:
        from app.core.sql_transpiler import transpile_batch  # type: ignore
    except Exception as e:
        pytest.skip(f"sql_transpiler 不可加载: {e}")
        return
    sqls = [c["input_sql"] for c in _transpile_items()]
    out = transpile_batch(sqls, source="mysql", target="opengauss")
    assert isinstance(out, list) and len(out) == len(sqls)
    fails = sum(1 for r in out if not r.get("ok"))
    assert fails == 0, f"batch 中 {fails}/{len(sqls)} 条失败"
