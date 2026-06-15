"""实时监控消融实验：异常检测 + 自动暂停 + 进度报告。

Usage:
    python -m eval.monitor_ablation [--max-restarts 3]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # zhixianyunshu/
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"
CHECKPOINT_FILE = RESULTS_DIR / "per_case_all_fast.json"
LOG_FILE = RESULTS_DIR / "per_case_ablation.log"
LOCK_FILE = RESULTS_DIR / ".ablation.lock"

# 异常阈值
MAX_ALL_FAIL_PER_CASE = 3       # 连续 N 个 case 全 FAIL → 暂停
MAX_CONSECUTIVE_ERRORS = 5      # 连续错误达此次数 → 暂停
LOG_STALE_TIMEOUT = 120         # 日志超过 N 秒无更新 → 进程可能死亡
PROGRESS_REPORT_INTERVAL = 5    # 每 N 个 case 报告一次进度


def _ts():
    return datetime.now().strftime("%H:%M:%S")


def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass
    return {}


def count_anomalies(checkpoint: dict) -> dict:
    """统计当前 checkpoint 中的异常。"""
    all_fail_count = 0
    partial_count = 0
    for cid, modes in checkpoint.items():
        ok = sum(1 for r in modes.values() if r.get("sql_ok"))
        if ok == 0:
            all_fail_count += 1
        elif ok < 5:
            partial_count += 1
    return {"all_fail": all_fail_count, "partial": partial_count, "total": len(checkpoint)}


def check_backend_health() -> bool:
    """检查后端是否健康。"""
    import urllib.request
    try:
        req = urllib.request.Request("http://localhost:8080/actuator/health", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "UP"
    except Exception:
        return False


def check_rag_health() -> bool:
    """检查 RAG 服务是否健康。"""
    import urllib.request
    try:
        req = urllib.request.Request("http://localhost:8004/health", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ok"
    except Exception:
        return False


def tail_log(n: int = 5) -> list[str]:
    """读取日志最后 N 行。"""
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return lines[-n:]
    except Exception:
        return []


def get_log_mtime() -> float:
    """获取日志文件最后修改时间。"""
    if LOG_FILE.exists():
        return LOG_FILE.stat().st_mtime
    return 0


def parse_completed_cases(log_lines: list[str]) -> list[str]:
    """从日志中解析已完成的 case ID。"""
    import re
    cases = []
    for line in log_lines:
        m = re.search(r"\[(\d+)/\d+\]\s+(\S+).*?→\s*通过:", line)
        if m:
            cases.append(m.group(2))
    return cases


def run_ablation(max_restarts: int = 3):
    """运行消融实验，带实时监控。"""
    print(f"[{_ts()}] === 消融实验监控启动 ===", flush=True)
    print(f"[{_ts()}] max_restarts={max_restarts}", flush=True)

    # 前置检查
    if not check_backend_health():
        print(f"[{_ts()}] [ERROR] 后端不健康！请先启动后端。", flush=True)
        return
    if not check_rag_health():
        print(f"[{_ts()}] [ERROR] RAG 服务不健康！请先启动 RAG。", flush=True)
        return
    print(f"[{_ts()}] [OK] 后端和 RAG 服务均健康", flush=True)
    print(f"[{_ts()}] [OK] PROJECT_ROOT = {PROJECT_ROOT}", flush=True)

    checkpoint = load_checkpoint()
    stats = count_anomalies(checkpoint)
    print(f"[{_ts()}] [OK] Checkpoint: {stats['total']}/96 cases (ALL FAIL: {stats['all_fail']})", flush=True)

    for restart_i in range(max_restarts + 1):
        if restart_i > 0:
            print(f"\n[{_ts()}] [RESTART] 第 {restart_i}/{max_restarts} 次重启...", flush=True)
            time.sleep(10)
            # 清理锁
            if LOCK_FILE.exists():
                try:
                    LOCK_FILE.unlink()
                except Exception:
                    pass

        print(f"\n[{_ts()}] [START] 启动消融进程...", flush=True)

        # 启动消融进程
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        proc = subprocess.Popen(
            [sys.executable, "-m", "eval.ablation",
             "--per-case", "--fast", "--cooldown", "15", "--pair", "all", "--force"],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print(f"[{_ts()}] [OK] 进程启动 PID={proc.pid}", flush=True)

        last_report_case = 0
        last_log_check = time.time()
        consecutive_stale = 0
        last_checkpoint_count = len(load_checkpoint())

        try:
            while proc.poll() is None:
                time.sleep(10)  # 每 10 秒检查一次

                # 1. 检查日志是否停滞
                log_mtime = get_log_mtime()
                if time.time() - log_mtime > LOG_STALE_TIMEOUT:
                    consecutive_stale += 1
                    print(f"[{_ts()}] [WARN] 日志 {LOG_STALE_TIMEOUT}s 无更新 (连续第 {consecutive_stale} 次)", flush=True)
                    if consecutive_stale >= 3:
                        print(f"[{_ts()}] [ALERT] 日志持续无更新，进程可能已死！终止进程。", flush=True)
                        proc.terminate()
                        time.sleep(5)
                        if proc.poll() is None:
                            proc.kill()
                        break
                else:
                    consecutive_stale = 0

                # 2. 检查后端健康
                if not check_backend_health():
                    print(f"[{_ts()}] [ALERT] 后端不健康！终止进程。", flush=True)
                    proc.terminate()
                    time.sleep(5)
                    if proc.poll() is None:
                        proc.kill()
                    break

                # 3. 检查 checkpoint 进度和异常
                checkpoint = load_checkpoint()
                current_count = len(checkpoint)
                stats = count_anomalies(checkpoint)

                # 进度报告
                if current_count >= last_report_case + PROGRESS_REPORT_INTERVAL:
                    last_report_case = current_count
                    elapsed_min = (time.time() - log_mtime + LOG_STALE_TIMEOUT) / 60
                    print(f"[{_ts()}] [PROGRESS] {current_count}/96 cases | "
                          f"ALL PASS: {current_count - stats['all_fail'] - stats['partial']} | "
                          f"PARTIAL: {stats['partial']} | ALL FAIL: {stats['all_fail']}", flush=True)

                    # 打印最近的 per-case 结果
                    recent = list(checkpoint.items())[-PROGRESS_REPORT_INTERVAL:]
                    for cid, modes in recent:
                        ok = [m for m, r in modes.items() if r.get("sql_ok")]
                        fail = [m for m, r in modes.items() if not r.get("sql_ok")]
                        tag = "ALL PASS" if len(ok) == 5 else f"OK:{len(ok)}/5"
                        print(f"  {cid}: {tag} {('FAIL: ' + ','.join(fail)) if fail else ''}", flush=True)

                # 4. 检查新增 ALL FAIL
                new_all_fail = 0
                for cid, modes in checkpoint.items():
                    if not any(r.get("sql_ok") for r in modes.values()):
                        new_all_fail += 1
                if new_all_fail >= MAX_ALL_FAIL_PER_CASE:
                    print(f"[{_ts()}] [ALERT] ALL FAIL case 数达 {new_all_fail}，超过阈值 {MAX_ALL_FAIL_PER_CASE}！终止进程。", flush=True)
                    proc.terminate()
                    time.sleep(5)
                    if proc.poll() is None:
                        proc.kill()
                    break

                # 5. 读取进程输出（非阻塞）
                try:
                    import select
                    if hasattr(select, 'select'):
                        ready, _, _ = select.select([proc.stdout], [], [], 0)
                        if ready:
                            line = proc.stdout.readline()
                            if line:
                                line = line.strip()
                                # 检测关键错误
                                if "ERROR" in line or "FATAL" in line or "Connection refused" in line:
                                    print(f"[{_ts()}] [ERR] {line}", flush=True)
                except (OSError, ValueError):
                    pass  # Windows 不支持 select on pipes

                last_checkpoint_count = current_count

        except KeyboardInterrupt:
            print(f"\n[{_ts()}] [INTERRUPT] 用户中断，终止进程...", flush=True)
            proc.terminate()
            time.sleep(3)
            if proc.poll() is None:
                proc.kill()
            return

        # 进程结束
        exit_code = proc.poll()
        if exit_code == 0:
            print(f"\n[{_ts()}] [DONE] 消融进程正常完成！", flush=True)
            break
        else:
            print(f"\n[{_ts()}] [EXIT] 进程退出码: {exit_code}", flush=True)
            if restart_i >= max_restarts:
                print(f"[{_ts()}] [FATAL] 已达最大重试次数 ({max_restarts})，退出。", flush=True)
                break

    # 最终报告
    checkpoint = load_checkpoint()
    stats = count_anomalies(checkpoint)
    print(f"\n{'='*60}", flush=True)
    print(f"[{_ts()}] === 最终报告 ===", flush=True)
    print(f"  完成: {stats['total']}/96 cases", flush=True)
    print(f"  ALL PASS: {stats['total'] - stats['all_fail'] - stats['partial']}", flush=True)
    print(f"  PARTIAL: {stats['partial']}", flush=True)
    print(f"  ALL FAIL: {stats['all_fail']}", flush=True)
    print(f"{'='*60}", flush=True)

    # 列出 ALL FAIL cases
    if stats['all_fail'] > 0:
        print(f"\n[ALL FAIL cases]:", flush=True)
        for cid, modes in checkpoint.items():
            if not any(r.get("sql_ok") for r in modes.values()):
                errors = [r.get("error", "unknown")[:80] for r in modes.values() if r.get("error")]
                print(f"  {cid}: {errors[0] if errors else 'no error info'}", flush=True)


def main():
    ap = argparse.ArgumentParser(description="实时监控消融实验")
    ap.add_argument("--max-restarts", type=int, default=3, help="最大重启次数")
    args = ap.parse_args()
    run_ablation(max_restarts=args.max_restarts)


if __name__ == "__main__":
    main()
