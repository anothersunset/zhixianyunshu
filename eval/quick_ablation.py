"""快速消融：10 个代表性 case × 5 组检索配置，验证趋势。"""
from __future__ import annotations

import atexit
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from eval.judge import LLMJudge
from eval.migration_client import MigrationClient
from eval.run_eval import RETRIEVAL_CHOICES, evaluate, load_dataset, summarize

LOG_FILE = Path("eval/results/quick_ablation.log").resolve()
LOCK_FILE = Path("eval/results/.quick_ablation.lock").resolve()


def _pid_alive(pid: int) -> bool:
    """检查 PID 是否仍在运行（跨平台）。"""
    if sys.platform == "win32":
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in r.stdout
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def _acquire_lock(force: bool = False):
    """获取进程锁。如果已有实例在运行则退出。"""
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            if _pid_alive(old_pid):
                if force:
                    _print(f"[lock] 强制覆盖旧进程 (PID={old_pid})")
                else:
                    _print(f"[FATAL] 另一个 quick_ablation 进程 (PID={old_pid}) 正在运行！", flush=True)
                    _print(f"  如需强制运行，请使用 --force 参数，或手动终止 PID {old_pid}", flush=True)
                    sys.exit(1)
            else:
                _print(f"[lock] 旧进程 (PID={old_pid}) 已死，清理 lock 文件")
        except (ValueError, OSError):
            pass

    LOCK_FILE.write_text(str(os.getpid()))

    def _cleanup():
        try:
            if LOCK_FILE.exists() and LOCK_FILE.read_text().strip() == str(os.getpid()):
                LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    atexit.register(_cleanup)
    # 注册信号处理（SIGINT/SIGTERM）
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda s, f: (_cleanup(), sys.exit(0)))
        except (OSError, ValueError):
            pass  # Windows 下某些信号不可用


def _release_lock():
    """释放进程锁。"""
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text().strip() == str(os.getpid()):
            LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass

def _print(*args, **kwargs):
    """输出到终端 + 日志文件。"""
    msg = " ".join(str(a) for a in args)
    kwargs.setdefault("flush", True)
    print(msg, **kwargs)
    sys.stdout.flush()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

GROUP_LABEL = {
    "bm25": "A · BM25 only",
    "vector": "B · Vector only",
    "vector_rerank": "C · Vector + Rerank",
    "crag": "D · + CRAG",
    "full": "E · + GraphRAG / CKG",
}

# 10 个代表性 case，覆盖不同 pair 和难度
REPRESENTATIVE_IDS = [
    "mysql_opengauss_001",  # IFNULL → COALESCE
    "mysql_opengauss_002",  # AUTO_INCREMENT → SERIAL
    "mysql_opengauss_003",  # ENUM → VARCHAR+CHECK
    "mysql_opengauss_004",  # LIMIT offset
    "mysql_opengauss_005",  # GROUP_CONCAT → STRING_AGG
    "mysql_postgresql_001", # ENUM → CREATE TYPE
    "mysql_postgresql_002", # ON DUPLICATE KEY → ON CONFLICT
    "oracle_opengauss_001", # DECODE → CASE
    "oracle_opengauss_002", # ROWNUM → LIMIT
    "oracle_opengauss_003", # NVL → COALESCE
]


def select_representative(cases, n=10):
    """选择代表性 case。如果 ID 不在数据集中，取前 n 个。"""
    by_id = {c["id"]: c for c in cases}
    selected = []
    for rid in REPRESENTATIVE_IDS:
        if rid in by_id:
            selected.append(by_id[rid])
    # 补足到 n 个
    if len(selected) < n:
        for c in cases:
            if c not in selected:
                selected.append(c)
            if len(selected) >= n:
                break
    return selected[:n]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="快速消融实验")
    parser.add_argument("--force", action="store_true", help="强制运行，即使已有实例在运行")
    args = parser.parse_args()

    # 进程锁：防止多个实例同时运行
    _acquire_lock(force=args.force)
    _print(f"[lock] PID={os.getpid()} 已获取锁")

    client = MigrationClient(cooldown=20)
    judge = None  # 跳过 Judge，减少一半 LLM 调用
    _print("[INFO] Judge disabled for speed")
    all_cases = load_dataset("eval/datasets", "all")
    cases = select_representative(all_cases, 10)

    _print(f"Selected {len(cases)} cases: {[c['id'] for c in cases]}")
    table = {}
    results_dir = Path("eval/results").resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    case_ids = [c["id"] for c in cases]

    for i, r in enumerate(RETRIEVAL_CHOICES):
        ckpt = results_dir / f"quick_ablation_{r}.json"
        # 断点续跑：已有完整结果则跳过
        cached_rows = []
        if ckpt.exists():
            try:
                cached = json.load(open(ckpt, encoding="utf-8"))
                cached_rows = cached.get("rows", [])
                if len(cached_rows) == len(cases):
                    _print(f"[{i+1}/5] {GROUP_LABEL[r]}: 已有完整结果，跳过")
                    table[r] = cached
                    continue
                elif len(cached_rows) > 0:
                    _print(f"[{i+1}/5] {GROUP_LABEL[r]}: 发现 {len(cached_rows)}/{len(cases)} 行，断点续跑...")
                    done_ids = {row["id"] for row in cached_rows}
                    remaining = [c for c in cases if c["id"] not in done_ids]
                    rows = evaluate(remaining, r, client, judge, fast=True, parallel=1,
                                    checkpoint_path=str(ckpt), checkpoint_base_rows=cached_rows)
                    all_rows = cached_rows + rows
                    s = summarize(all_rows)
                    table[r] = {"summary": s, "rows": all_rows}
                    with open(ckpt, "w", encoding="utf-8") as fh:
                        json.dump({"summary": s, "rows": all_rows}, fh, ensure_ascii=False, indent=2)
                    _print(f"[{i+1}/5] {GROUP_LABEL[r]}: 续跑完成 "
                          f"Recall@5={s.get('recall@5', 'N/A')}, SQL修复率={s.get('sql_repair_rate', 'N/A')}")
                    continue
            except (json.JSONDecodeError, KeyError):
                cached_rows = []

        _print(f"\n[{i+1}/5] {GROUP_LABEL[r]}: evaluating {len(cases)} cases...")
        t0 = time.time()
        rows = evaluate(cases, r, client, judge, fast=True, parallel=1,
                        checkpoint_path=str(ckpt))
        elapsed = time.time() - t0
        s = summarize(rows)
        table[r] = {"summary": s, "rows": rows}
        _print(f"[{i+1}/5] {GROUP_LABEL[r]}: done ({elapsed:.0f}s) "
              f"Recall@5={s.get('recall@5', 'N/A')}, SQL修复率={s.get('sql_repair_rate', 'N/A')}")

        # 保存最终结果
        with open(ckpt, "w", encoding="utf-8") as fh:
            json.dump({"summary": s, "rows": rows}, fh, ensure_ascii=False, indent=2)

    # 生成汇总表
    _print("\n" + "=" * 70)
    _print("| 组别 | Recall@5 | SQL 修复率 | 报告准确率 | n |")
    _print("|---|---|---|---|---|")
    for r in RETRIEVAL_CHOICES:
        s = table[r]["summary"]
        rec = s.get("recall@5")
        rec_str = f"{rec:.4f}" if rec is not None else "N/A"
        _print(f"| {GROUP_LABEL[r]} | {rec_str} | {s.get('sql_repair_rate')} | {s.get('report_accuracy')} | {s.get('n')} |")

    # 保存完整结果
    with open(results_dir / "quick-ablation.json", "w", encoding="utf-8") as fh:
        json.dump({k: v["summary"] for k, v in table.items()}, fh, ensure_ascii=False, indent=2)
    _print("\nResults saved to eval/results/quick-ablation.json")


if __name__ == "__main__":
    main()
