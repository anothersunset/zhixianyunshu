"""消融：跑全部 5 组检索配置并汇总成对比表。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from eval.judge import LLMJudge
from eval.migration_client import MigrationClient
from eval.run_eval import RETRIEVAL_CHOICES, _eval_one, evaluate, load_dataset, summarize

LOCK_FILE = Path("eval/results/.ablation.lock")


def _acquire_lock():
    """防止多个消融进程同时运行。"""
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            # 检查进程是否还在
            if sys.platform == "win32":
                import subprocess
                r = subprocess.run(["tasklist", "/FI", f"PID eq {old_pid}"],
                                   capture_output=True, text=True, timeout=5)
                if str(old_pid) in r.stdout:
                    print(f"[FATAL] 另一个消融进程 (PID={old_pid}) 正在运行！请先杀掉它。", flush=True)
                    sys.exit(1)
            else:
                os.kill(old_pid, 0)
                print(f"[FATAL] 另一个消融进程 (PID={old_pid}) 正在运行！", flush=True)
                sys.exit(1)
        except (ValueError, OSError, ProcessLookupError):
            pass  # 旧进程已死，可以继续
    LOCK_FILE.write_text(str(os.getpid()))


def _release_lock():
    """释放进程锁。"""
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def wait_for_backend(base_url: str, timeout: float = 120) -> bool:
    """等待后端就绪，最多 timeout 秒。返回 True 表示就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/actuator/health", timeout=5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        print("[health] 等待后端就绪...", flush=True)
        time.sleep(5)
    return False

GROUP_LABEL = {
    "bm25": "A · BM25 only",
    "vector": "B · Vector only",
    "vector_rerank": "C · Vector + Rerank",
    "crag": "D · + CRAG",
    "full": "E · + GraphRAG / CKG",
}


def _make_checkpoint_saver(checkpoint_file: Path, cached_rows: list):
    """创建一个可靠的 checkpoint 保存回调，使用绝对路径。"""
    abs_path = checkpoint_file.resolve()

    def _save(done_rows):
        try:
            all_rows = cached_rows + done_rows
            partial = {"summary": summarize(all_rows), "rows": all_rows}
            # 写临时文件再 rename，防止写入中断导致文件损坏
            tmp_path = abs_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(partial, fh, ensure_ascii=False, indent=2)
            tmp_path.replace(abs_path)
            print(f"  [checkpoint] {len(all_rows)} rows -> {abs_path.name}", flush=True)
        except Exception as e:
            print(f"  [checkpoint] ERROR: {e}", flush=True)

    return _save


def run_all(dataset="eval/datasets", pair="all", use_judge=True, fast=False, parallel=1, cooldown=None):
    client = MigrationClient(cooldown=cooldown)
    judge = LLMJudge() if use_judge else None
    cases = load_dataset(dataset, pair)
    table = {}

    # 断点续跑：检查已有结果
    suffix = "_fast" if fast else ""
    results_dir = Path("eval/results").resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    for i, r in enumerate(RETRIEVAL_CHOICES):
        checkpoint_file = results_dir / f"raw_{r}_{pair}{suffix}.json"
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, encoding="utf-8") as fh:
                    cached = json.load(fh)
                if "summary" in cached and "rows" in cached:
                    cached_n = len(cached["rows"])
                    if cached_n == len(cases):
                        print(f"[{i+1}/5] {GROUP_LABEL[r]}: 已有完整结果，跳过 (n={cached_n})", flush=True)
                        table[r] = {"summary": cached["summary"], "rows": cached["rows"]}
                        continue
                    elif cached_n > 0:
                        print(f"[{i+1}/5] {GROUP_LABEL[r]}: 发现部分结果 ({cached_n}/{len(cases)})，断点续跑...", flush=True)
                        # 从断点继续：跳过已完成的 case
                        done_ids = {row["id"] for row in cached["rows"]}
                        remaining = [c for c in cases if c["id"] not in done_ids]
                        if remaining:
                            ckpt_str = str(checkpoint_file.resolve())
                            new_rows = evaluate(remaining, r, client, judge, fast=fast, parallel=parallel,
                                                checkpoint_path=ckpt_str, checkpoint_base_rows=cached["rows"])
                            rows = cached["rows"] + new_rows
                        else:
                            rows = cached["rows"]
                        elapsed = 0
                        s = summarize(rows)
                        table[r] = {"summary": s, "rows": rows}
                        print(f"[{i+1}/5] {GROUP_LABEL[r]}: 续跑完成 "
                              f"Recall@5={s.get('recall@5', 'N/A')}, SQL修复率={s.get('sql_repair_rate', 'N/A')}", flush=True)
                        with open(checkpoint_file, "w", encoding="utf-8") as fh:
                            json.dump(table[r], fh, ensure_ascii=False, indent=2)
                        continue
            except (json.JSONDecodeError, KeyError):
                pass  # 文件损坏，重新跑

        # 健康检查：确保后端就绪
        if not wait_for_backend(client.base_url):
            print(f"[{i+1}/5] {GROUP_LABEL[r]}: 后端不可用，跳过", flush=True)
            continue

        print(f"[{i+1}/5] {GROUP_LABEL[r]}: 开始评估 {len(cases)} 用例...", flush=True)
        t0 = time.time()

        ckpt_str = str(checkpoint_file.resolve())
        rows = evaluate(cases, r, client, judge, fast=fast, parallel=parallel,
                        checkpoint_path=ckpt_str)
        elapsed = time.time() - t0
        s = summarize(rows)
        table[r] = {"summary": s, "rows": rows}
        print(f"[{i+1}/5] {GROUP_LABEL[r]}: 完成 ({elapsed:.0f}s) "
              f"Recall@5={s.get('recall@5', 'N/A')}, SQL修复率={s.get('sql_repair_rate', 'N/A')}", flush=True)

        # 立即写入中间结果（断点续跑用）
        with open(checkpoint_file, "w", encoding="utf-8") as fh:
            json.dump(table[r], fh, ensure_ascii=False, indent=2)

    return table


def _save_per_case_checkpoint(ckpt_file, checkpoint):
    """保存 per-case checkpoint（原子写入）。"""
    try:
        tmp_path = str(ckpt_file) + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(checkpoint, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(ckpt_file))
    except Exception as e:
        print(f"  [checkpoint] ERROR: {e}", flush=True)


def _print_interim(checkpoint: dict, done: int, total: int, t_start: float):
    """每 N 个 case 输出中间汇总表。"""
    elapsed = time.time() - t_start
    print(f"\n{'─' * 60}")
    print(f"[interim] {done}/{total} cases ({elapsed/60:.1f}m elapsed)")
    print(f"| {'组别':20s} | Recall@5 | SQL修复率 | 报告准确率 | n |")
    print(f"|{'-'*22}|{'-'*10}|{'-'*10}|{'-'*10}|{'-'*4}|")
    for mode in RETRIEVAL_CHOICES:
        rows = [checkpoint[cid].get(mode, {}) for cid in checkpoint if mode in checkpoint.get(cid, {})]
        if not rows:
            continue
        s = summarize(rows)
        rec = s.get("recall@5")
        if rec is not None:
            rec_str = f"{rec:.4f}"
        else:
            rec_str = "N/A"
        sql = s.get('sql_repair_rate', 'N/A')
        sql_str = f"{sql:.4f}" if isinstance(sql, (int, float)) else str(sql)
        acc = s.get('report_accuracy', 'N/A')
        acc_str = f"{acc:.4f}" if isinstance(acc, (int, float)) else str(acc)
        n_str = str(s.get('n', 'N/A'))
        print(f"| {GROUP_LABEL[mode]:20s} | {rec_str:>8s} | {sql_str:>8s} | {acc_str:>8s} | {n_str:>2s} |")
    print(f"{'─' * 60}\n", flush=True)


def run_all_per_case(dataset="eval/datasets", pair="all", use_judge=True, fast=False, cooldown=None):
    """Per-case 模式：每个 case 并行跑 A-E 全部 5 组，方便 per-case 对比分析。

    优化：5 个模式并发执行（ThreadPoolExecutor），冷却在 case 间而非请求间。
    """
    client = MigrationClient(cooldown=cooldown)
    judge = LLMJudge() if use_judge else None
    cases = load_dataset(dataset, pair)
    results_dir = Path("eval/results").resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    # checkpoint 结构: {case_id: {mode: row_dict, ...}, ...}
    ckpt_file = results_dir / f"per_case_{pair}{'_fast' if fast else ''}.json"
    checkpoint = {}
    if ckpt_file.exists():
        try:
            checkpoint = json.load(open(ckpt_file, encoding="utf-8"))
            print(f"[per-case] 加载 checkpoint: {len(checkpoint)} cases 已完成", flush=True)
        except (json.JSONDecodeError, KeyError):
            pass

    total = len(cases)
    t_start = time.time()

    for ci, case in enumerate(cases):
        cid = case["id"]
        if cid in checkpoint and len(checkpoint[cid]) == len(RETRIEVAL_CHOICES):
            print(f"[{ci+1}/{total}] {cid}: 已完成，跳过", flush=True)
            continue

        # case 间冷却（第一个 case 不冷却）
        if ci > 0 and cid not in checkpoint:
            client.batch_throttle()

        # 确定本 case 需要跑的模式
        case_results = checkpoint.get(cid, {})
        remaining_modes = [m for m in RETRIEVAL_CHOICES if m not in case_results]

        if not remaining_modes:
            continue

        print(f"\n[{ci+1}/{total}] {cid} ({case['pair']}): 并行跑 {len(remaining_modes)} 组...", flush=True)
        t_case = time.time()

        # 并行执行 5 个模式（skip_throttle=True，冷却由 case 层面控制）
        with ThreadPoolExecutor(max_workers=5) as mode_pool:
            futures = {
                mode_pool.submit(_eval_one, case, mode, client, judge, fast, True): mode
                for mode in remaining_modes
            }
            for fut in as_completed(futures):
                mode = futures[fut]
                try:
                    row = fut.result()
                    tag = "OK" if row["sql_ok"] else "FAIL"
                    print(f"  {GROUP_LABEL[mode]}: {tag}", flush=True)
                except Exception as e:
                    row = {"id": cid, "pair": case["pair"], "sql_ok": False, "error": str(e)}
                    print(f"  {GROUP_LABEL[mode]}: ERROR {e}", flush=True)

                case_results[mode] = row
                checkpoint[cid] = case_results
                _save_per_case_checkpoint(ckpt_file, checkpoint)

        case_elapsed = time.time() - t_case
        ok_modes = [m for m in RETRIEVAL_CHOICES if case_results.get(m, {}).get("sql_ok")]
        print(f"  → 通过: {', '.join(ok_modes) if ok_modes else '无'} ({case_elapsed:.0f}s)", flush=True)

        # 每 5 个 case 输出一次中间汇总
        completed_so_far = ci + 1
        if completed_so_far % 5 == 0:
            _print_interim(checkpoint, completed_so_far, total, t_start)

    total_elapsed = time.time() - t_start
    print(f"\n[per-case] 全部完成，总耗时 {total_elapsed/60:.1f} 分钟", flush=True)

    # 转换为 table 格式并输出汇总
    table = {}
    for mode in RETRIEVAL_CHOICES:
        rows = [checkpoint[cid].get(mode, {}) for cid in checkpoint if mode in checkpoint[cid]]
        table[mode] = {"summary": summarize(rows), "rows": rows}

    return table


def to_markdown(table) -> str:
    head = "| 组别 | Recall@5 | SQL 修复成功率 | 迁移报告准确率 | n |"
    sep = "|---|---|---|---|---|"
    lines = [head, sep]
    for r in RETRIEVAL_CHOICES:
        s = table[r]["summary"]
        rec = s.get("recall@5")
        rec_str = f"{rec:.4f}" if rec is not None else "N/A"
        lines.append("| {0} | {1} | {2} | {3} | {4} |".format(
            GROUP_LABEL[r],
            rec_str,
            s.get("sql_repair_rate"),
            s.get("report_accuracy"),
            s.get("n"),
        ))
    return "\n".join(lines)


def main():
    _acquire_lock()
    try:
        ap = argparse.ArgumentParser()
        ap.add_argument("--dataset", default="eval/datasets")
        ap.add_argument("--pair", default="all")
        ap.add_argument("--use-judge", action="store_true")
        ap.add_argument("--fast", action="store_true",
                        help="快速模式：跳过 AgentGraph，用 chat-model 模拟不同检索等级")
        ap.add_argument("--parallel", type=int, default=1)
        ap.add_argument("--cooldown", type=float, default=None,
                        help="两次请求之间的最小间隔秒数（防后端过载，默认 3）")
        ap.add_argument("--per-case", action="store_true",
                        help="Per-case 模式：每个 case 依次跑 A-E 全部 5 组")
        args = ap.parse_args()

        if args.per_case:
            table = run_all_per_case(args.dataset, args.pair, args.use_judge, fast=args.fast, cooldown=args.cooldown)
        else:
            table = run_all(args.dataset, args.pair, args.use_judge, fast=args.fast, parallel=args.parallel, cooldown=args.cooldown)
        md = to_markdown(table)
        Path("eval/results").mkdir(parents=True, exist_ok=True)
        suffix = "_fast" if args.fast else ""
        mode_suffix = "_per_case" if args.per_case else ""
        with open(f"eval/results/p1-ablation{suffix}{mode_suffix}.md", "w", encoding="utf-8") as fh:
            fh.write(md + "\n")
        with open(f"eval/results/p1-ablation{suffix}{mode_suffix}.json", "w", encoding="utf-8") as fh:
            json.dump({k: v["summary"] for k, v in table.items()}, fh, ensure_ascii=False, indent=2)
        print("\n" + md, flush=True)
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
