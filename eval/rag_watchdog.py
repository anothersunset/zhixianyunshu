"""RAG 服务守护脚本 — 专业级单实例 watchdog。

根因分析：
  之前的 watchdog 没有进程锁，导致多个实例同时运行。RAG 崩溃时多个 watchdog
  同时检测到并同时重启，产生多个 RAG 实例抢端口 → 连锁崩溃死循环。

修复策略：
  1. 进程锁（PID 文件）：确保只有一个 watchdog 运行
  2. 重启冷却期：重启后 60s 内不重新检测，避免误判
  3. 启动前端口清理：重启前确保端口完全释放
  4. 优雅退出：Ctrl+C 时自动释放锁
  5. 连续失败退避：连续失败时延长检查间隔

用法: python eval/rag_watchdog.py
"""
import atexit
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

RAG_PORT = 8001
RAG_DIR = os.path.join(os.path.dirname(__file__), "..", "zhiqian", "rag")
CHECK_INTERVAL = 15        # 正常检查间隔（秒）
STARTUP_GRACE = 45         # 重启后等待启动的宽限期（秒）
MAX_RESTARTS = 30          # 最大重启次数（超过后退出，防止无限循环）
MEMORY_THRESHOLD_MB = 2800 # 内存阈值（MB），超过触发预防性重启
COOLDOWN_AFTER_RESTART = 60  # 重启后冷却期（秒），期间不触发新的重启
LOCK_FILE = Path(os.path.join(os.path.dirname(__file__), "results", ".rag_watchdog.lock"))


# ============================================================
# 进程锁
# ============================================================

def _acquire_lock():
    """获取 watchdog 进程锁，确保单实例运行。"""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            if sys.platform == "win32":
                r = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {old_pid}"],
                    capture_output=True, text=True, timeout=5,
                )
                if str(old_pid) in r.stdout:
                    print(f"[FATAL] 另一个 watchdog (PID={old_pid}) 正在运行！退出。", flush=True)
                    sys.exit(1)
            else:
                os.kill(old_pid, 0)
                print(f"[FATAL] 另一个 watchdog (PID={old_pid}) 正在运行！退出。", flush=True)
                sys.exit(1)
        except (ValueError, OSError, ProcessLookupError):
            pass  # 旧进程已死，可以继续
    LOCK_FILE.write_text(str(os.getpid()))


def _release_lock():
    """释放 watchdog 进程锁。"""
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# ============================================================
# 端口 / 进程工具
# ============================================================

def _get_pid_on_port(port: int) -> int | None:
    """获取监听指定端口的进程 PID。"""
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = int(parts[-1])
                return pid
    except Exception:
        pass
    return None


def _wait_port_free(port: int, timeout: float = 10) -> bool:
    """等待端口释放，返回 True 表示端口已空闲。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _get_pid_on_port(port) is None:
            return True
        time.sleep(0.5)
    return False


def _get_process_memory_mb(pid: int) -> float:
    """获取指定 PID 的内存使用（MB）。"""
    try:
        tl = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        for line in tl.stdout.splitlines():
            if "python" in line.lower():
                parts = line.split(",")
                if len(parts) >= 5:
                    mem_str = parts[4].strip('"').replace(",", "").replace(" K", "")
                    return float(mem_str) / 1024
    except Exception:
        pass
    return -1.0


# ============================================================
# RAG 健康检查
# ============================================================

def is_rag_healthy() -> tuple[bool, str]:
    """检查 RAG 是否健康。返回 (healthy, reason)。"""
    # 1. 端口检查
    pid = _get_pid_on_port(RAG_PORT)
    if pid is None:
        return False, "port not listening"

    # 2. HTTP 健康检查
    try:
        import urllib.request
        resp = urllib.request.urlopen(f"http://localhost:{RAG_PORT}/health", timeout=8)
        if resp.status != 200:
            return False, f"HTTP {resp.status}"
        data = json.loads(resp.read())
        mem = data.get("memory_mb", 0)

        # 3. 内存检查
        if mem > MEMORY_THRESHOLD_MB:
            return False, f"memory too high: {mem:.0f}MB > {MEMORY_THRESHOLD_MB}MB"

        return True, f"OK (pid={pid}, mem={mem:.0f}MB)"
    except Exception as e:
        return False, f"HTTP error: {e}"


# ============================================================
# RAG 生命周期管理
# ============================================================

def kill_rag():
    """杀死所有占用 RAG 端口的进程。"""
    killed = []
    for _ in range(3):  # 最多清理 3 轮
        pid = _get_pid_on_port(RAG_PORT)
        if pid is None:
            break
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=5)
            killed.append(pid)
        except Exception:
            pass
        time.sleep(1)

    if killed:
        print(f"[watchdog] Killed RAG PIDs: {killed}", flush=True)
    _wait_port_free(RAG_PORT, timeout=15)
    return len(killed) > 0


def start_rag() -> int | None:
    """启动 RAG 服务，返回 PID。"""
    rag_dir = os.path.abspath(RAG_DIR)
    log_path = "/tmp/rag.log"
    env = os.environ.copy()
    env["HF_HUB_OFFLINE"] = "1"
    env["RAG_QDRANT_URL"] = "http://localhost:6333"
    env["RAG_USE_RERANKER"] = "false"

    with open(log_path, "a", encoding="utf-8") as log_f:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "0.0.0.0", "--port", str(RAG_PORT)],
            cwd=rag_dir,
            env=env,
            stdout=log_f,
            stderr=subprocess.STDOUT,
        )
    return proc.pid


def restart_rag() -> bool:
    """完整重启流程：杀旧进程 → 等端口释放 → 启动新进程 → 等待健康。"""
    print("[watchdog] ===== RAG 重启流程开始 =====", flush=True)

    # Step 1: 杀死旧进程
    kill_rag()

    # Step 2: 确保端口完全释放
    if not _wait_port_free(RAG_PORT, timeout=15):
        print("[watchdog] WARNING: 端口未释放，强制再杀一次", flush=True)
        kill_rag()
        if not _wait_port_free(RAG_PORT, timeout=10):
            print("[watchdog] ERROR: 端口仍被占用，放弃重启", flush=True)
            return False

    # Step 3: 启动新进程
    pid = start_rag()
    print(f"[watchdog] RAG started PID={pid}, 等待 {STARTUP_GRACE}s 启动...", flush=True)

    # Step 4: 等待启动完成
    time.sleep(STARTUP_GRACE)

    # Step 5: 验证健康
    healthy, reason = is_rag_healthy()
    if healthy:
        print(f"[watchdog] RAG 重启成功: {reason}", flush=True)
        return True
    else:
        print(f"[watchdog] RAG 重启后不健康: {reason}", flush=True)
        return False


# ============================================================
# 主循环
# ============================================================

def main():
    _acquire_lock()
    atexit.register(_release_lock)

    # 信号处理：优雅退出
    def _signal_handler(sig, frame):
        print(f"\n[watchdog] 收到信号 {sig}，退出...", flush=True)
        _release_lock()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    restarts = 0
    consecutive_failures = 0
    last_restart_time = 0.0

    print(f"[watchdog] Starting RAG watchdog (PID={os.getpid()}, port={RAG_PORT}, "
          f"interval={CHECK_INTERVAL}s, mem_limit={MEMORY_THRESHOLD_MB}MB)", flush=True)

    # 初始检查
    healthy, reason = is_rag_healthy()
    if not healthy:
        print(f"[watchdog] RAG not healthy: {reason}, starting...", flush=True)
        if restart_rag():
            restarts += 1
            last_restart_time = time.time()
        else:
            print("[watchdog] 初始启动失败！", flush=True)

    # 主循环
    while restarts < MAX_RESTARTS:
        time.sleep(CHECK_INTERVAL)

        # 冷却期内跳过检查
        if time.time() - last_restart_time < COOLDOWN_AFTER_RESTART:
            remaining = int(COOLDOWN_AFTER_RESTART - (time.time() - last_restart_time))
            if remaining % 15 == 0:
                print(f"[watchdog] 冷却期中 ({remaining}s remaining)", flush=True)
            continue

        healthy, reason = is_rag_healthy()

        if healthy:
            consecutive_failures = 0
            # 心跳日志（每 2 分钟一次）
            if int(time.time()) % 120 < CHECK_INTERVAL:
                print(f"[watchdog] RAG healthy: {reason} (restarts={restarts})", flush=True)
        else:
            consecutive_failures += 1
            print(f"[watchdog] RAG unhealthy: {reason} (consecutive={consecutive_failures})", flush=True)

            # 连续 2 次失败才触发重启（避免瞬时抖动误判）
            if consecutive_failures >= 2:
                print(f"[watchdog] 连续 {consecutive_failures} 次失败，触发重启 (restart #{restarts + 1})", flush=True)
                if restart_rag():
                    restarts += 1
                    last_restart_time = time.time()
                    consecutive_failures = 0
                else:
                    # 重启失败，延长等待
                    print("[watchdog] 重启失败，等待 120s 后重试...", flush=True)
                    time.sleep(120)

    print(f"[watchdog] Max restarts ({MAX_RESTARTS}) reached, exiting", flush=True)
    _release_lock()


if __name__ == "__main__":
    main()
