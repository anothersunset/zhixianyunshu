"""监控 retest 进度，用法: python eval/watch_retest.py [间隔秒，默认15]"""
import json, sys, time
from pathlib import Path

INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 15
PROGRESS_FILE = Path(__file__).resolve().parent.parent / "eval" / "results" / "retest_progress.json"

last_completed = -1
while True:
    if not PROGRESS_FILE.exists():
        print(f"[{time.strftime('%H:%M:%S')}] 等待开始...")
        time.sleep(INTERVAL)
        continue

    p = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    done = p["completed"]
    total = p["total"]
    pct = done / total * 100 if total else 0

    if done > last_completed:
        last_completed = done
        ok_rate = p["improved"] / done * 100 if done else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"[{time.strftime('%H:%M:%S')}] [{bar}] {done}/{total} ({pct:.0f}%)  "
              f"ok={p['improved']}/{done} ({ok_rate:.0f}%)  fail={p['still_fail']}  err={p['errors']}")

    if p.get("finished"):
        print(f"\n=== 完成 ===")
        print(f"改善率: {p['improved']}/{total} ({p['improved']/total*100:.1f}%)")
        if p["still_fail"]:
            print(f"仍失败:")
            for r in p["results"]:
                if not r["sql_ok"]:
                    print(f"  {r['case_id']} ({r['mode']})")
        break

    time.sleep(INTERVAL)
