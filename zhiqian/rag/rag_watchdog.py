"""RAG 服务看门狗 — 监控进程健康，自动重启崩溃的服务。

使用方式：
    python rag_watchdog.py                    # 前台运行
    python rag_watchdog.py --background       # 后台运行（nohup）
    python rag_watchdog.py --check            # 仅检查一次状态
    python rag_watchdog.py --stop             # 停止看门狗和 RAG 服务

功能：
    1. 定期检查 RAG 服务健康状态（/health 端点）
    2. 服务崩溃时自动重启（指数退避）
    3. 内存监控 — 超过阈值主动重启防止 OOM
    4. 完整日志记录到 rag_watchdog.log
    5. PID 文件管理，防止多实例
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ─── 配置 ───
RAG_PORT = 8004
RAG_HOST = "127.0.0.1"
HEALTH_URL = f"http://{RAG_HOST}:{RAG_PORT}/health"
HEALTH_TIMEOUT = 10  # 秒
CHECK_INTERVAL = 15  # 秒
MAX_MEMORY_MB = 5000  # MB，超过此值主动重启
MAX_RESTART_ATTEMPTS = 5  # 连续重启上限
RESTART_BACKOFF_BASE = 5  # 退避基数（秒）
RESTART_BACKOFF_MAX = 120  # 最大退避（秒）
PID_FILE = Path(__file__).parent / ".rag_watchdog.pid"
LOG_FILE = Path(__file__).parent / "rag_watchdog.log"

# RAG 启动环境
RAG_ENV = {
    "HF_HUB_OFFLINE": "1",
    "RAG_USE_RERANKER": "true",
    "RAG_RRF_K": "15",
    "RAG_RRF_CHANNEL_WEIGHTS": "1.0,1.0,0.5",
    "RAG_QDRANT_URL": "http://localhost:6333",
}
RAG_CWD = Path(__file__).parent
RAG_CMD = [sys.executable, "-m", "uvicorn", "app.main:app",
           "--port", str(RAG_PORT), "--host", "0.0.0.0"]

# ─── 日志 ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("rag_watchdog")


def write_pid():
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def read_pid() -> int | None:
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text(encoding="utf-8").strip())
        except ValueError:
            return None
    return None


def is_process_alive(pid: int) -> bool:
    """检查进程是否存活（跨平台）。"""
    try:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ProcessLookupError):
        return False


def check_health() -> tuple[bool, dict | None]:
    """检查 RAG 服务健康状态。返回 (healthy, info_dict)。"""
    try:
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            return True, data
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as e:
        return False, {"error": str(e)}


def get_process_memory_mb(pid: int) -> float | None:
    """获取进程内存使用（MB）。"""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return None
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            psapi = ctypes.windll.psapi
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                kernel32.CloseHandle(handle)
                return counters.WorkingSetSize / (1024 * 1024)
            kernel32.CloseHandle(handle)
            return None
        else:
            import resource
            # Linux: /proc/{pid}/status
            status_file = Path(f"/proc/{pid}/status")
            if status_file.exists():
                for line in status_file.read_text().splitlines():
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024
            return None
    except Exception:
        return None


def find_rag_process() -> int | None:
    """查找正在运行的 RAG uvicorn 进程 PID。"""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["wmic", "process", "where",
                 f"CommandLine like '%uvicorn%app.main%port%{RAG_PORT}%'",
                 "get", "ProcessId", "/FORMAT:VALUE"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.splitlines():
                if "ProcessId=" in line:
                    pid_str = line.split("=")[-1].strip()
                    if pid_str and pid_str.isdigit():
                        return int(pid_str)
        else:
            result = subprocess.run(
                ["pgrep", "-f", f"uvicorn.*app.main.*{RAG_PORT}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.stdout.strip():
                return int(result.stdout.strip().split()[0])
    except Exception:
        pass
    return None


def kill_process(pid: int):
    """终止进程。"""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=10)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(3)
            if is_process_alive(pid):
                os.kill(pid, signal.SIGKILL)
    except Exception as e:
        log.warning("终止进程 %d 失败: %s", pid, e)


def start_rag() -> subprocess.Popen | None:
    """启动 RAG 服务。返回 Popen 对象。"""
    env = os.environ.copy()
    env.update(RAG_ENV)
    try:
        log_file = RAG_CWD / "rag_service.log"
        lf = open(log_file, "a", encoding="utf-8")
        proc = subprocess.Popen(
            RAG_CMD,
            cwd=str(RAG_CWD),
            env=env,
            stdout=lf,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        log.info("RAG 服务启动: PID=%d, 日志=%s", proc.pid, log_file)
        return proc
    except Exception as e:
        log.error("启动 RAG 服务失败: %s", e)
        return None


def wait_for_ready(timeout: int = 120) -> bool:
    """等待 RAG 服务就绪。"""
    start = time.time()
    while time.time() - start < timeout:
        healthy, info = check_health()
        if healthy:
            log.info("RAG 服务就绪 (%.1fs)", time.time() - start)
            return True
        time.sleep(3)
    log.error("RAG 服务 %ds 内未就绪", timeout)
    return False


class Watchdog:
    def __init__(self):
        self.restart_count = 0
        self.last_restart = 0.0
        self.running = True
        self.rag_pid: int | None = None

    def handle_signal(self, signum, frame):
        log.info("收到信号 %d, 停止看门狗", signum)
        self.running = False

    def get_backoff(self) -> float:
        """指数退避时间。"""
        if self.restart_count == 0:
            return 0
        backoff = min(RESTART_BACKOFF_BASE * (2 ** (self.restart_count - 1)),
                      RESTART_BACKOFF_MAX)
        return backoff

    def restart_rag(self, reason: str) -> bool:
        """重启 RAG 服务。"""
        self.restart_count += 1
        if self.restart_count > MAX_RESTART_ATTEMPTS:
            log.error("连续重启 %d 次超过上限 %d，停止看门狗",
                      self.restart_count, MAX_RESTART_ATTEMPTS)
            return False

        backoff = self.get_backoff()
        if backoff > 0:
            log.info("退避等待 %.1fs (第 %d 次重启)", backoff, self.restart_count)
            time.sleep(backoff)

        log.info("重启 RAG 服务 (原因: %s, 第 %d 次)", reason, self.restart_count)

        # 先杀掉旧进程
        old_pid = find_rag_process()
        if old_pid:
            log.info("终止旧 RAG 进程 PID=%d", old_pid)
            kill_process(old_pid)
            time.sleep(2)

        # 启动新进程
        proc = start_rag()
        if proc is None:
            return False

        self.rag_pid = proc.pid
        if wait_for_ready():
            self.last_restart = time.time()
            return True
        return False

    def check_once(self) -> bool:
        """单次健康检查。返回 True 表示健康。"""
        healthy, info = check_health()
        if healthy:
            # 重置重启计数（服务稳定运行 60s 后）
            if self.restart_count > 0 and time.time() - self.last_restart > 60:
                log.info("RAG 服务稳定运行 60s，重置重启计数")
                self.restart_count = 0

            # 内存检查
            rag_pid = find_rag_process()
            if rag_pid:
                mem = get_process_memory_mb(rag_pid)
                if mem and mem > MAX_MEMORY_MB:
                    log.warning("RAG 内存 %.0fMB 超过阈值 %dMB，主动重启",
                                mem, MAX_MEMORY_MB)
                    self.restart_rag(f"内存超限 {mem:.0f}MB")
            return True
        else:
            log.warning("RAG 服务不健康: %s", info)
            return False

    def run(self):
        """主循环。"""
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        write_pid()
        log.info("看门狗启动 PID=%d, 检查间隔 %ds, 内存阈值 %dMB",
                 os.getpid(), CHECK_INTERVAL, MAX_MEMORY_MB)

        # 初始检查
        healthy, _ = check_health()
        if not healthy:
            log.info("RAG 服务未运行，启动中...")
            if not self.restart_rag("初始启动"):
                log.error("初始启动失败，退出")
                return

        while self.running:
            time.sleep(CHECK_INTERVAL)
            if not self.running:
                break
            if not self.check_once():
                if not self.restart_rag("健康检查失败"):
                    log.error("重启失败，退出看门狗")
                    break

        log.info("看门狗停止")
        self.cleanup()

    def cleanup(self):
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)


def cmd_check():
    """仅检查状态。"""
    healthy, info = check_health()
    rag_pid = find_rag_process()
    mem = get_process_memory_mb(rag_pid) if rag_pid else None

    print(f"RAG 服务: {'健康' if healthy else '不健康'}")
    print(f"PID: {rag_pid or '未找到'}")
    print(f"内存: {mem:.0f}MB" if mem else "内存: 未知")
    if info:
        print(f"详情: {json.dumps(info, ensure_ascii=False, indent=2)}")

    # 检查看门狗
    wd_pid = read_pid()
    if wd_pid and is_process_alive(wd_pid):
        print(f"看门狗: 运行中 (PID={wd_pid})")
    else:
        print("看门狗: 未运行")


def cmd_stop():
    """停止看门狗和 RAG 服务。"""
    # 停止看门狗
    wd_pid = read_pid()
    if wd_pid and is_process_alive(wd_pid):
        log.info("停止看门狗 PID=%d", wd_pid)
        kill_process(wd_pid)
    elif wd_pid:
        log.info("看门狗 PID=%d 已不存活", wd_pid)

    # 停止 RAG
    rag_pid = find_rag_process()
    if rag_pid:
        log.info("停止 RAG 服务 PID=%d", rag_pid)
        kill_process(rag_pid)

    if PID_FILE.exists():
        PID_FILE.unlink(missing_ok=True)
    print("已停止看门狗和 RAG 服务")


def main():
    parser = argparse.ArgumentParser(description="RAG 服务看门狗")
    parser.add_argument("--check", action="store_true", help="仅检查状态")
    parser.add_argument("--stop", action="store_true", help="停止看门狗和 RAG")
    parser.add_argument("--background", action="store_true", help="后台运行")
    args = parser.parse_args()

    if args.check:
        cmd_check()
        return

    if args.stop:
        cmd_stop()
        return

    # 检查是否已有看门狗在运行
    wd_pid = read_pid()
    if wd_pid and is_process_alive(wd_pid):
        print(f"看门狗已在运行 (PID={wd_pid})，请先 --stop")
        return

    watchdog = Watchdog()
    watchdog.run()


if __name__ == "__main__":
    main()
