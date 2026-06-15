"""半量消融：48 cases × 5 组，边跑边分析。"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from eval.judge import LLMJudge
from eval.migration_client import MigrationClient
from eval.run_eval import RETRIEVAL_CHOICES, evaluate, load_dataset, summarize

RESULTS_DIR = Path("eval/results").resolve()
CHECKPOINT = RESULTS_DIR / "per_case_all_fast.json"
LOG = RESULTS_DIR / "half_ablation.log"

def _log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_checkpoint():
    if CHECKPOINT.exists():
        try:
            with open(CHECKPOINT, encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_checkpoint(data):
    tmp = CHECKPOINT.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(CHECKPOINT)

def analyze_so_far(data):
    """实时分析当前结果。"""
    if not data:
        return
    _log(f"\n{'='*60}")
    _log(f"实时分析 ({len(data)}/48 完成)")

    # SQL repair rate per mode
    mode_stats = {}
    for mode in RETRIEVAL_CHOICES:
        ok = sum(1 for m in data.values() if m.get(mode, {}).get("sql_ok"))
        total = sum(1 for m in data.values() if mode in m)
        rate = ok / total if total else 0
        mode_stats[mode] = (ok, total, rate)
        _log(f"  {mode}: {ok}/{total} = {rate:.1%}")

    # Monotonicity check
    rates = [mode_stats[m][2] for m in RETRIEVAL_CHOICES]
    mono = all(rates[i] <= rates[i+1] for i in range(len(rates)-1))
    _log(f"  A→E 单调递增: {'YES' if mono else 'NO'}")
    if not mono:
        for i in range(len(rates)-1):
            if rates[i] > rates[i+1]:
                _log(f"    ↓ {RETRIEVAL_CHOICES[i]}({rates[i]:.1%}) > {RETRIEVAL_CHOICES[i+1]}({rates[i+1]:.1%})")

    # ALL FAIL cases
    all_fail = [cid for cid, m in data.items() if not any(r.get("sql_ok") for r in m.values())]
    if all_fail:
        _log(f"  ALL FAIL: {all_fail}")
    _log(f"{'='*60}\n")

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--cooldown", type=float, default=15)
    ap.add_argument("--judge", action="store_true")
    args = ap.parse_args()

    # Load all cases, select 48 evenly
    all_cases = load_dataset("eval/datasets", pair="all")
    # Select every other case to get ~48
    cases = all_cases[::2][:48]
    _log(f"Selected {len(cases)}/{len(all_cases)} cases (half)")

    checkpoint = load_checkpoint()
    client = MigrationClient(cooldown=args.cooldown)
    judge = LLMJudge() if args.judge else None

    # Run each case through all 5 modes
    for ci, case in enumerate(cases):
        cid = case["id"]
        if cid in checkpoint and len(checkpoint[cid]) >= 5:
            _log(f"[{ci+1}/{len(cases)}] {cid}: 已完成，跳过")
            continue

        _log(f"[{ci+1}/{len(cases)}] {cid} ({case['pair']}): 并行跑 5 组...")
        case_result = checkpoint.get(cid, {})
        t0 = time.time()

        for mode in RETRIEVAL_CHOICES:
            if mode in case_result:
                continue
            try:
                result = evaluate(
                    cases=[case],
                    client=client,
                    retrieval=mode,
                    judge=judge,
                    fast=args.fast,
                )
                # evaluate() returns a list of dicts
                if isinstance(result, list) and len(result) > 0:
                    row = result[0]
                elif isinstance(result, dict) and result.get("rows"):
                    row = result["rows"][0]
                else:
                    _log(f"  {mode}: FAIL (no result)")
                    case_result[mode] = {"sql_ok": False, "error": "no result"}
                    continue
                case_result[mode] = row
                ok = "OK" if row.get("sql_ok") else "FAIL"
                _log(f"  {mode}: {ok}")
            except Exception as e:
                _log(f"  {mode}: FAIL ({e})")
                case_result[mode] = {"sql_ok": False, "error": str(e)[:200]}

        checkpoint[cid] = case_result
        save_checkpoint(checkpoint)
        elapsed = time.time() - t0
        ok_modes = [m for m, r in case_result.items() if r.get("sql_ok")]
        _log(f"  → 通过: {', '.join(ok_modes)} ({elapsed:.0f}s)")

        # 每 5 个 case 分析一次
        if (ci + 1) % 5 == 0:
            analyze_so_far(checkpoint)

    # Final analysis
    _log("\n" + "="*60)
    _log("最终结果")
    analyze_so_far(checkpoint)

    # Save summary
    summary = summarize(list(checkpoint.values()))
    _log(f"\nSummary: {json.dumps(summary, indent=2)}")

if __name__ == "__main__":
    main()
