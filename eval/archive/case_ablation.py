"""Case-level ablation: 每个 case 跑完全部检索组，逐 case 对比分析。

与 ablation.py 不同：这里按 case 循环，每个 case 跑 4 组检索，
再进入下一个 case。方便逐 case 对比和中途分析。

用法:
  python -u -m eval.case_ablation --pair all --fast --cooldown 15
  python -u -m eval.case_ablation --pair mysql_opengauss --fast --cooldown 12
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from eval.migration_client import MigrationClient
from eval.run_eval import RETRIEVAL_CHOICES, summarize, _target_db
from eval.metrics import recall_at_k, sql_equivalent, report_point_hit_rate

RESULTS_DIR = Path("eval/results").resolve()
LOCK_FILE = RESULTS_DIR / ".case_ablation.lock"

# 消融组（跳过 vector_rerank，减少 API 调用）
ABLATION_MODES = ["bm25", "vector", "crag", "full"]


def _acquire_lock():
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            if sys.platform == "win32":
                import subprocess
                r = subprocess.run(["tasklist", "/FI", f"PID eq {old_pid}"],
                                   capture_output=True, text=True, timeout=5)
                if str(old_pid) in r.stdout:
                    print(f"[FATAL] 另一个进程 (PID={old_pid}) 正在运行！", flush=True)
                    sys.exit(1)
            else:
                os.kill(old_pid, 0)
                sys.exit(1)
        except (ValueError, OSError, ProcessLookupError):
            pass
    LOCK_FILE.write_text(str(os.getpid()))


def _release_lock():
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    print(msg, **kwargs, flush=True)
    log_file = RESULTS_DIR / "case_ablation.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def _load_dataset(path: str, pair: str) -> list[dict]:
    import glob
    if pair == "all":
        files = sorted(glob.glob(os.path.join(path, "*.jsonl")))
    else:
        files = [os.path.join(path, pair + ".jsonl")]
    cases = []
    for f in files:
        with open(f, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    cases.append(json.loads(line))
    return cases


def _safe_pair(pair: str) -> str:
    return pair.replace("->", "_")


def _load_checkpoint(pair: str) -> dict:
    """加载已有结果，返回 {case_id: {mode: result_row, ...}}"""
    path = RESULTS_DIR / f"case_ablation_{_safe_pair(pair)}.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # 格式: {"results": {case_id: {mode: row, ...}}, "rows": [...]}
        if "results" in data:
            return data["results"]
        return {}
    except (json.JSONDecodeError, KeyError):
        return {}


def _clean_nan(value):
    """清理 NaN 值，JSON 不支持 NaN。"""
    import math
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _save_checkpoint(pair: str, results: dict):
    """原子写入 checkpoint。"""
    path = RESULTS_DIR / f"case_ablation_{_safe_pair(pair)}.json"
    # 转换为 flat rows，清理 NaN
    rows = []
    for cid, modes in results.items():
        for mode, row in modes.items():
            cleaned = {k: _clean_nan(v) for k, v in row.items()}
            rows.append(cleaned)
    data = {"results": results, "rows": rows, "summary": summarize(rows)}
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(str(tmp), str(path))


def _eval_one_case(client: MigrationClient, case: dict, mode: str) -> dict:
    """评估单个 case 的单个检索模式。"""
    target = _target_db(case["pair"])
    try:
        res = client.run_migration(
            source_sql=case["source_sql"], pair=case["pair"],
            retrieval=mode, fast=True
        )
        parse_failed = not res.target_sql and res.risk_level == "high"
        if parse_failed:
            return {
                "id": case["id"], "mode": mode, "pair": case["pair"],
                "sql_ok": False, "report_acc": 0.0,
                "recall@5": recall_at_k(res.retrieved_ids, case.get("gold_context_ids", []), k=5),
                "risk_level": "parse_failed", "pred_sql": "", "error": "LLM parse failed",
            }
        ok = sql_equivalent(res.target_sql, case["gold_target_sql"], target)
        report_acc = report_point_hit_rate(res.report_points, case.get("gold_report_points", []), None)
        recall = recall_at_k(res.retrieved_ids, case.get("gold_context_ids", []), k=5)
        import math
        if recall is not None and math.isnan(recall):
            recall = None
        return {
            "id": case["id"], "mode": mode, "pair": case["pair"],
            "sql_ok": bool(ok), "report_acc": report_acc,
            "recall@5": recall,
            "risk_level": res.risk_level, "pred_sql": res.target_sql, "error": None,
        }
    except Exception as e:
        return {
            "id": case["id"], "mode": mode, "pair": case["pair"],
            "sql_ok": False, "report_acc": 0.0, "recall@5": None,
            "risk_level": "error", "pred_sql": "", "error": str(e)[:120],
        }


def main():
    _acquire_lock()
    try:
        ap = argparse.ArgumentParser()
        ap.add_argument("--pair", default="all")
        ap.add_argument("--dataset", default="eval/datasets")
        ap.add_argument("--cooldown", type=float, default=15)
        ap.add_argument("--start", type=int, default=0, help="从第 N 个 case 开始（跳过前 N 个）")
        args = ap.parse_args()

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        client = MigrationClient(cooldown=args.cooldown)
        cases = _load_dataset(args.dataset, args.pair)

        # pair 级别循环
        if args.pair == "all":
            pairs = sorted(set(c["pair"] for c in cases))
        else:
            pairs = [args.pair]

        for pair in pairs:
            pair_cases = [c for c in cases if c["pair"] == pair]
            if not pair_cases:
                continue

            results = _load_checkpoint(pair)
            done_ids = set(results.keys())
            remaining = [c for c in pair_cases if c["id"] not in done_ids]
            if args.start > 0:
                remaining = remaining[args.start:]

            _print(f"\n{'='*60}")
            _print(f"Pair: {pair} | 已完成: {len(done_ids)} | 剩余: {len(remaining)} | 总计: {len(pair_cases)}")
            _print(f"{'='*60}")

            for ci, case in enumerate(remaining):
                case_id = case["id"]
                _print(f"\n--- [{len(done_ids)+ci+1}/{len(pair_cases)}] {case_id} ---")
                case_results = results.get(case_id, {})

                for mode in ABLATION_MODES:
                    if mode in case_results:
                        r = case_results[mode]
                        tag = "OK" if r["sql_ok"] else "FAIL"
                        _print(f"  {mode:12s}: [cached] {tag}")
                        continue

                    r = _eval_one_case(client, case, mode)
                    case_results[mode] = r
                    tag = "OK" if r["sql_ok"] else "FAIL"
                    err = f" [{r['error'][:40]}]" if r.get("error") else ""
                    _print(f"  {mode:12s}: {tag} sql={r['sql_ok']} report={r['report_acc']:.2f}{err}")

                    # 每个 mode 完成后立即保存
                    results[case_id] = case_results
                    _save_checkpoint(pair, results)

                # 逐 case 汇总
                ok_modes = [m for m in ABLATION_MODES if case_results.get(m, {}).get("sql_ok")]
                _print(f"  -> 通过: {ok_modes if ok_modes else '无'}")

            # pair 完成，输出汇总
            _print(f"\n{'='*60}")
            _print(f"Pair {pair} 完成汇总:")
            for mode in ABLATION_MODES:
                mode_rows = [results[cid].get(mode, {}) for cid in results if mode in results.get(cid, {})]
                ok = sum(1 for r in mode_rows if r.get("sql_ok"))
                n = len(mode_rows)
                rate = ok / n if n else 0
                _print(f"  {mode:12s}: {ok}/{n} ({rate:.1%})")

        _print(f"\n结果保存: {RESULTS_DIR / f'case_ablation_*.json'}")

    finally:
        _release_lock()


if __name__ == "__main__":
    main()
