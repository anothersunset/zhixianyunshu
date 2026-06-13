"""后端服务守护脚本 — 检测宕机自动重启，每 15 秒检查一次。"""
import subprocess
import time
import sys
import os

BACKEND_PORT = 8080
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "zhiqian", "backend")
CHECK_INTERVAL = 15
MAX_RESTARTS = 30


def is_backend_up() -> bool:
    """检查后端是否存活。"""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("127.0.0.1", BACKEND_PORT))
        s.close()
        return result == 0
    except Exception:
        return False


def kill_backend():
    """杀死后端进程。"""
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if f":{BACKEND_PORT}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=5)
                print(f"[watchdog] Killed backend PID={pid}", flush=True)
                return True
    except Exception as e:
        print(f"[watchdog] Kill failed: {e}", flush=True)
    return False


def restart_backend():
    """重启后端服务。"""
    kill_backend()
    time.sleep(5)

    backend_dir = os.path.abspath(BACKEND_DIR)
    log_path = "/tmp/backend.log"

    with open(log_path, "a") as log_f:
        proc = subprocess.Popen(
            [sys.executable, "-c", "import subprocess; subprocess.run(['./mvnw', 'spring-boot:run', '-Dspring-boot.run.profiles=local'])"],
            cwd=backend_dir,
            stdout=log_f,
            stderr=subprocess.STDOUT,
        )
    print(f"[watchdog] Backend restarted PID={proc.pid}", flush=True)
    return proc.pid


def main():
    restarts = 0
    print(f"[watchdog] Starting backend watchdog (port={BACKEND_PORT}, interval={CHECK_INTERVAL}s)", flush=True)

    if not is_backend_up():
        print("[watchdog] Backend not up, starting...", flush=True)
        restart_backend()
        restarts += 1
        time.sleep(60)

    while restarts < MAX_RESTARTS:
        time.sleep(CHECK_INTERVAL)
        if not is_backend_up():
            print(f"[watchdog] Backend DOWN! Restarting... (restart #{restarts + 1})", flush=True)
            restart_backend()
            restarts += 1
            time.sleep(60)
        else:
            if int(time.time()) % 120 < CHECK_INTERVAL:
                print(f"[watchdog] Backend UP (restarts={restarts})", flush=True)

    print(f"[watchdog] Max restarts ({MAX_RESTARTS}) reached, exiting", flush=True)


if __name__ == "__main__":
    main()
