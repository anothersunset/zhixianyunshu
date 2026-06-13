"""健康检查端点 — 增加内存监控和模型状态。"""
from fastapi import APIRouter
import logging
import os

router = APIRouter()
log = logging.getLogger(__name__)


def _get_memory_mb() -> float:
    """获取当前进程内存使用 (MB)。"""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    except ImportError:
        # psutil 未装时用 Windows 特定方法
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetCurrentProcess()
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_ulong),
                            ("PageFaultCount", ctypes.c_ulong),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            kernel32.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
            return counters.WorkingSetSize / 1024 / 1024
        except Exception:
            return -1.0


@router.get("/health")
async def health():
    mem_mb = _get_memory_mb()
    return {
        "status": "ok",
        "memory_mb": round(mem_mb, 1),
        "pid": os.getpid(),
    }
