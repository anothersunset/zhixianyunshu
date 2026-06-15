"""只跑 vector_rerank + crag + full 三个 reranker 模式。

用于修复 FlagEmbedding 后补跑所有 case 的 reranker 模式。
会覆盖 checkpoint 中旧的（无 reranker 降级的）结果。

用法:
  python -m eval.run_rerank_only --pair all --fast
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
from eval.run_eval import _eval_one, load_dataset, summarize
from eval.judge import LLMJudge
from eval.migration_client import MigrationClient

RERANK_MODES = ["vector_rerank", "crag", "full"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="eval/datasets")
    ap.add_argument("--pair", default="all")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--use-judge", action="store_true")
    ap.add_argument("--cooldown", type=float, default=None)
    ap.add_argument("--force-rerun", action="store_true",
                    help="强制重跑所有 case（覆盖已有结果）")
    args = ap.parse_args()

    client = MigrationClient(cooldown=args.cooldown)
    judge = LLMJudge() if args.use_judge else None
    cases = load_dataset(args.dataset, args.pair)
    results_dir = Path("eval/results").resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    ckpt_file = results_dir / "per_case_all_fast.json"
    checkpoint = {}
    if ckpt_file.exists():
        checkpoint = json.load(open(ckpt_file, encoding="utf-8"))
        print(f"[rerank-only] Loaded checkpoint: {len(checkpoint)} cases")

    total = len(cases)
    t_start = time.time()
    done = 0
    skipped = 0

    for ci, case in enumerate(cases):
        cid = case["id"]
        case_results = checkpoint.get(cid, {})

        if args.force_rerun:
            # 强制重跑：删掉旧的 reranker 结果
            for mode in RERANK_MODES:
                case_results.pop(mode, None)
        else:
            # 智能跳过：如果已有 reranker 结果且没有 error，跳过
            has_all = all(
                mode in case_results and not case_results[mode].get("error")
                for mode in RERANK_MODES
            )
            if has_all:
                skipped += 1
                continue

        missing = [m for m in RERANK_MODES if m not in case_results or case_results[m].get("error")]
        if not missing:
            skipped += 1
            continue

        print(f"[{ci+1}/{total}] {cid}: running {missing}...", flush=True)
        for mode in missing:
            try:
                row = _eval_one(case, mode, client, judge, args.fast, skip_throttle=False)
                case_results[mode] = row
                tag = "OK" if row.get("sql_ok") else "FAIL"
                print(f"  {mode}: {tag}", flush=True)
            except Exception as e:
                case_results[mode] = {"id": cid, "pair": case["pair"], "sql_ok": False, "error": str(e)}
                print(f"  {mode}: ERROR {e}", flush=True)

        checkpoint[cid] = case_results
        tmp = str(ckpt_file) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        import os; os.replace(tmp, str(ckpt_file))
        done += 1

    elapsed = time.time() - t_start
    print(f"\n[rerank-only] Done: {done} cases run, {skipped} skipped, {elapsed/60:.1f} min")

    for mode in RERANK_MODES:
        rows = [checkpoint[cid].get(mode, {}) for cid in checkpoint if mode in checkpoint[cid]]
        s = summarize(rows)
        print(f"  {mode}: n={s.get('n')}, SQL={s.get('sql_repair_rate')}, Recall={s.get('recall@5')}")


if __name__ == "__main__":
    main()
