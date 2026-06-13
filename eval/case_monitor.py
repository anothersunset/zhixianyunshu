"""逐 case 监控：每当新 case 完成，立即分析测试结果。

用法：python -u -m eval.case_monitor
"""
from __future__ import annotations

import json
import time
from pathlib import Path

RESULTS_DIR = Path("eval/results").resolve()
RETRIEVAL_MODES = ["bm25", "vector", "vector_rerank", "crag", "full"]
MODE_LABELS = {
    "bm25": "A-BM25", "vector": "B-Vector",
    "vector_rerank": "C-Rerank", "crag": "D-CRAG", "full": "E-GraphRAG",
}


def _load_rows(mode: str) -> list[dict]:
    path = RESULTS_DIR / f"raw_{mode}_all_fast.json"
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("rows", [])
    except (json.JSONDecodeError, KeyError):
        return []


def _analyze_case(case_id: str, all_results: dict[str, dict]):
    """分析单个 case 在所有模式下的表现。"""
    print(f"\n{'='*60}")
    print(f"Case: {case_id}")
    print(f"{'='*60}")

    for mode in RETRIEVAL_MODES:
        row = all_results.get(mode)
        if row is None:
            print(f"  {MODE_LABELS[mode]:12s}: pending")
            continue

        tag = "OK" if row["sql_ok"] else "FAIL"
        err = f" [{row.get('error', '')[:50]}]" if row.get("error") else ""
        recall = row.get("recall@5")
        recall_str = f"{recall:.2f}" if recall is not None else "N/A"
        report = row.get("report_acc", 0)
        print(f"  {MODE_LABELS[mode]:12s}: {tag} | SQL={row['sql_ok']} | Recall@5={recall_str} | Report={report:.2f}{err}")

    # 汇总
    ok_modes = [m for m in RETRIEVAL_MODES if all_results.get(m, {}).get("sql_ok")]
    fail_modes = [m for m in RETRIEVAL_MODES if m in all_results and not all_results[m].get("sql_ok")]
    print(f"  -> 通过: {ok_modes if ok_modes else '无'}")
    if fail_modes:
        print(f"  -> 失败: {fail_modes}")


def _print_summary(mode: str, rows: list[dict]):
    """打印当前模式的汇总统计。"""
    if not rows:
        return
    n = len(rows)
    ok = sum(1 for r in rows if r.get("sql_ok"))
    rate = ok / n * 100

    # 按 pair 分组统计
    by_pair = {}
    for r in rows:
        pair = r.get("pair", "unknown")
        if pair not in by_pair:
            by_pair[pair] = {"total": 0, "ok": 0}
        by_pair[pair]["total"] += 1
        if r.get("sql_ok"):
            by_pair[pair]["ok"] += 1

    print(f"\n--- {MODE_LABELS[mode]} 汇总 ({n}/96) ---")
    print(f"  SQL 修复率: {ok}/{n} ({rate:.1f}%)")
    for pair, stats in sorted(by_pair.items()):
        prate = stats["ok"] / stats["total"] * 100 if stats["total"] else 0
        print(f"    {pair}: {stats['ok']}/{stats['total']} ({prate:.0f}%)")


def main():
    print("逐 case 监控开始，等待新 case 完成...")
    print(f"监控目录: {RESULTS_DIR}")

    # 记录已分析的 case
    analyzed = set()  # (case_id, mode)
    prev_counts = {m: 0 for m in RETRIEVAL_MODES}

    while True:
        current_counts = {}
        for mode in RETRIEVAL_MODES:
            rows = _load_rows(mode)
            current_counts[mode] = len(rows)

            # 检查新模式数据
            if len(rows) > prev_counts.get(mode, 0):
                # 有新 case 完成
                for row in rows:
                    key = (row["id"], mode)
                    if key not in analyzed:
                        analyzed.add(key)
                        # 加载该 case 在所有模式下的结果
                        case_results = {}
                        for m in RETRIEVAL_MODES:
                            for r in _load_rows(m):
                                if r["id"] == row["id"]:
                                    case_results[m] = r
                        _analyze_case(row["id"], case_results)

                # 打印当前模式汇总
                _print_summary(mode, rows)

        prev_counts = current_counts

        # 检查是否全部完成
        all_done = all(current_counts.get(m, 0) >= 96 for m in RETRIEVAL_MODES)
        if all_done:
            print("\n\n全部完成！最终汇总：")
            for mode in RETRIEVAL_MODES:
                _print_summary(mode, _load_rows(mode))
            break

        time.sleep(10)


if __name__ == "__main__":
    main()
