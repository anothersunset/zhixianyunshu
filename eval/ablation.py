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


def _acquire_lock(force=False):
    """防止多个消融进程同时运行。force=True 时强制获取锁。"""
    if LOCK_FILE.exists():
        try:
            content = LOCK_FILE.read_text().strip()
            old_pid = int(content)
            # 检查进程是否还在
            if sys.platform == "win32":
                import subprocess
                r = subprocess.run(["tasklist", "/FI", f"PID eq {old_pid}"],
                                   capture_output=True, text=True, timeout=5)
                if str(old_pid) in r.stdout:
                    if force:
                        print(f"[warn] 强制覆盖旧锁 (PID={old_pid})", flush=True)
                    else:
                        print(f"[FATAL] 另一个消融进程 (PID={old_pid}) 正在运行！用 --force 强制覆盖。", flush=True)
                        sys.exit(1)
            else:
                os.kill(old_pid, 0)
                if force:
                    print(f"[warn] 强制覆盖旧锁 (PID={old_pid})", flush=True)
                else:
                    print(f"[FATAL] 另一个消融进程 (PID={old_pid}) 正在运行！用 --force 强制覆盖。", flush=True)
                    sys.exit(1)
        except (ValueError, OSError, ProcessLookupError):
            pass  # 旧进程已死或文件损坏，可以继续
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
    def _fmt(v):
        return f"{v:.4f}" if isinstance(v, (int, float)) else "N/A"

    print(f"\n{'─' * 72}")
    print(f"[interim] {done}/{total} cases ({elapsed/60:.1f}m elapsed)")
    # MRR@10 是排序敏感指标：rerank/CRAG 只改排序不改命中集合，Recall 会饱和看不出梯度，MRR 才能。
    print(f"| {'组别':20s} | Recall@5 | MRR@10 | SQL修复率 | 报告准确率 | n | mock检索 |")
    print(f"|{'-'*22}|{'-'*10}|{'-'*8}|{'-'*10}|{'-'*10}|{'-'*4}|{'-'*10}|")
    dirty_total = 0
    for mode in RETRIEVAL_CHOICES:
        rows = [checkpoint[cid].get(mode, {}) for cid in checkpoint if mode in checkpoint.get(cid, {})]
        if not rows:
            continue
        s = summarize(rows)
        dirty = s.get("mock_retrieval_cases", 0)
        dirty_total += dirty
        print(f"| {GROUP_LABEL[mode]:20s} | {_fmt(s.get('recall@5')):>8s} | {_fmt(s.get('mrr@10')):>6s} | "
              f"{_fmt(s.get('sql_repair_rate')):>8s} | {_fmt(s.get('report_accuracy')):>8s} | "
              f"{str(s.get('n', 'N/A')):>2s} | {str(dirty):>8s} |")
    if dirty_total:
        print(f"  [WARN] {dirty_total} 个 case 检索降级到后端 mock，本轮梯度不可采信——先修 RAG（见 preflight 能力探针）。")
    print(f"{'─' * 72}\n", flush=True)


def run_all_per_case(dataset="eval/datasets", pair="all", use_judge=True, fast=False, cooldown=None,
                     max_workers=2, max_consecutive_errors=10, limit=0):
    """Per-case 模式：每个 case 并行跑 A-E 全部 5 组，方便 per-case 对比分析。

    优化：max_workers 个模式并发执行（默认 2，避免后端过载），冷却在 case 间而非请求间。
    容错：每个 case 独立 try/except，单个 case 失败不影响整体进度。
          连续失败达 max_consecutive_errors 次时暂停 120s 冷却。
    """
    client = MigrationClient(cooldown=cooldown)
    judge = LLMJudge() if use_judge else None
    cases = load_dataset(dataset, pair)
    results_dir = Path("eval/results").resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    # 日志文件（独立于 stdout，防止 nohup 吞输出）
    log_file = results_dir / "per_case_ablation.log"
    try:
        _log_fh = open(log_file, "a", encoding="utf-8")
    except Exception:
        _log_fh = None

    def _log(msg: str):
        print(msg, flush=True)
        if _log_fh:
            try:
                _log_fh.write(msg + "\n")
                _log_fh.flush()
            except Exception:
                pass

    # 限制 case 数量
    if limit > 0:
        cases = cases[:limit]
        _log(f"[per-case] 限制为前 {limit} 个 case")

    # checkpoint 结构: {case_id: {mode: row_dict, ...}, ...}
    ckpt_file = results_dir / f"per_case_{pair}{'_fast' if fast else ''}.json"
    checkpoint = {}
    if ckpt_file.exists():
        try:
            checkpoint = json.load(open(ckpt_file, encoding="utf-8"))
            _log(f"[per-case] 加载 checkpoint: {len(checkpoint)} cases 已完成")
        except (json.JSONDecodeError, KeyError):
            pass

    total = len(cases)
    t_start = time.time()
    consecutive_errors = 0
    backend_ok_until = 0  # 上次后端健康检查通过的时间

    for ci, case in enumerate(cases):
        cid = case["id"]
        if cid in checkpoint and len(checkpoint[cid]) == len(RETRIEVAL_CHOICES):
            _log(f"[{ci+1}/{total}] {cid}: 已完成，跳过")
            continue

        # 每 10 个 case 或连续错误后检查后端健康
        now = time.time()
        if ci % 10 == 0 or consecutive_errors > 0 or now - backend_ok_until > 120:
            if not wait_for_backend(client.base_url, timeout=60):
                _log(f"[{ci+1}/{total}] 后端不可用，暂停 30s 后重试...")
                time.sleep(30)
                if not wait_for_backend(client.base_url, timeout=60):
                    _log(f"[{ci+1}/{total}] 后端持续不可用，跳过本 case")
                    continue
            backend_ok_until = time.time()

        # case 间冷却（第一个 case 不冷却）
        if ci > 0 and cid not in checkpoint:
            client.batch_throttle()

        # 连续错误过多时暂停冷却
        if consecutive_errors >= max_consecutive_errors:
            _log(f"  *** 连续 {consecutive_errors} 个 case 出错，暂停 120s 冷却...")
            time.sleep(120)
            consecutive_errors = 0
            # 冷却后重新检查后端
            if not wait_for_backend(client.base_url, timeout=60):
                _log(f"  *** 冷却后后端仍不可用，退出")
                break

        # 确定本 case 需要跑的模式
        case_results = checkpoint.get(cid, {})
        remaining_modes = [m for m in RETRIEVAL_CHOICES if m not in case_results]

        if not remaining_modes:
            continue

        _log(f"\n[{ci+1}/{total}] {cid} ({case['pair']}): 并行跑 {len(remaining_modes)} 组 (workers={max_workers})...")
        t_case = time.time()

        try:
            # 并行执行模式（skip_throttle=True，冷却由 case 层面控制）
            with ThreadPoolExecutor(max_workers=max_workers) as mode_pool:
                futures = {
                    mode_pool.submit(_eval_one, case, mode, client, judge, fast, True): mode
                    for mode in remaining_modes
                }
                for fut in as_completed(futures):
                    mode = futures[fut]
                    try:
                        row = fut.result(timeout=180)  # 单个模式最多 3 分钟
                        tag = "OK" if row["sql_ok"] else "FAIL"
                        _log(f"  {GROUP_LABEL[mode]}: {tag}")
                    except Exception as e:
                        row = {"id": cid, "pair": case["pair"], "sql_ok": False, "error": str(e)}
                        _log(f"  {GROUP_LABEL[mode]}: ERROR {e}")

                    case_results[mode] = row
                    checkpoint[cid] = case_results
                    _save_per_case_checkpoint(ckpt_file, checkpoint)

            consecutive_errors = 0  # 成功则重置
            backend_ok_until = time.time()  # 更新健康时间
        except Exception as e:
            consecutive_errors += 1
            _log(f"  *** CASE {cid} 异常: {e} (连续错误={consecutive_errors})")
            # 为未完成的模式填充错误结果
            for mode in remaining_modes:
                if mode not in case_results:
                    case_results[mode] = {"id": cid, "pair": case["pair"], "sql_ok": False, "error": str(e)}
            checkpoint[cid] = case_results
            _save_per_case_checkpoint(ckpt_file, checkpoint)

        case_elapsed = time.time() - t_case
        ok_modes = [m for m in RETRIEVAL_CHOICES if case_results.get(m, {}).get("sql_ok")]
        _log(f"  → 通过: {', '.join(ok_modes) if ok_modes else '无'} ({case_elapsed:.0f}s)")

        # 每 5 个 case 输出一次中间汇总
        completed_so_far = ci + 1
        if completed_so_far % 5 == 0:
            _print_interim(checkpoint, completed_so_far, total, t_start)

    total_elapsed = time.time() - t_start
    _log(f"\n[per-case] 全部完成，总耗时 {total_elapsed/60:.1f} 分钟")
    if _log_fh:
        _log_fh.close()

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
    ap.add_argument("--auto-restart", type=int, default=0, metavar="N",
                    help="内部自动重试 N 次（不再需要 bash watchdog）")
    ap.add_argument("--max-workers", type=int, default=2,
                    help="per-case 模式下每个 case 的并行模式数（默认 2，避免后端过载）")
    ap.add_argument("--max-consecutive-errors", type=int, default=10,
                    help="连续错误达此次数后暂停冷却（默认 10）")
    ap.add_argument("--force", action="store_true",
                    help="强制获取进程锁（覆盖残留锁文件）")
    ap.add_argument("--limit", type=int, default=0,
                    help="限制 case 数量（0=不限制，用于快速验证）")
    args = ap.parse_args()

    _acquire_lock(force=args.force)
    try:
        max_restarts = args.auto_restart
        for restart_i in range(max_restarts + 1):
            if restart_i > 0:
                print(f"\n[auto-restart] 第 {restart_i}/{max_restarts} 次重启（等待 10s）...", flush=True)
                time.sleep(10)
                _release_lock()
                _acquire_lock(force=True)

            try:
                if args.per_case:
                    table = run_all_per_case(args.dataset, args.pair, args.use_judge, fast=args.fast,
                                              cooldown=args.cooldown, max_workers=args.max_workers,
                                              max_consecutive_errors=args.max_consecutive_errors,
                                              limit=args.limit)
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
                break  # 成功完成，退出重试循环

            except KeyboardInterrupt:
                print("\n[ablation] 用户中断，退出", flush=True)
                break
            except Exception as e:
                print(f"\n[ablation] 未捕获异常: {type(e).__name__}: {e}", flush=True)
                import traceback
                traceback.print_exc()
                if restart_i >= max_restarts:
                    print(f"[ablation] 已达最大重试次数 ({max_restarts})，退出", flush=True)
                    raise
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
