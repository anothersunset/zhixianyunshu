"""全量重测所有历史失败 case×mode 组合，进度写入 retest_progress.json。"""
import json, requests, time, sys, glob
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import sql_equivalent

PROGRESS_FILE = Path(__file__).resolve().parent.parent / "eval" / "results" / "retest_progress.json"
CHECKPOINT_FILE = Path(__file__).resolve().parent.parent / "eval" / "results" / "per_case_all_fast.json"

# 加载 checkpoint
with open(CHECKPOINT_FILE, encoding="utf-8") as f:
    checkpoint = json.load(f)

# 加载数据集
dataset = {}
for f in sorted(glob.glob(str(Path(__file__).resolve().parent / "datasets" / "*.jsonl"))):
    with open(f, encoding="utf-8-sig") as fh:
        for line in fh:
            if line.strip():
                c = json.loads(line.strip())
                dataset[c["id"]] = c

# 找出所有失败 case×mode
failed = []
for case_id, modes in checkpoint.items():
    for mode_name, result in modes.items():
        if not result.get("sql_ok", True):
            cdata = dataset.get(case_id)
            if not cdata:
                continue
            pair = cdata.get("pair", "")
            failed.append({
                "case_id": case_id,
                "mode": mode_name,
                "pair": pair,
                "source_sql": cdata.get("source_sql", ""),
                "gold_sql": cdata.get("gold_target_sql", ""),
                "target_dialect": pair.split("->")[-1] if "->" in pair else "postgresql",
            })

total = len(failed)
print(f"[retest] {total} failed case×mode to retest, backend=http://localhost:8080")

# 初始化进度文件
progress = {
    "started": datetime.now().isoformat(),
    "total": total,
    "completed": 0,
    "improved": 0,
    "still_fail": 0,
    "errors": 0,
    "results": [],
    "finished": False,
}
PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

for i, fc in enumerate(failed, 1):
    try:
        payload = {"source_sql": fc["source_sql"], "pair": fc["pair"], "retrieval": fc["mode"], "fast": True}
        resp = requests.post("http://localhost:8080/migrate", json=payload, timeout=180)
        pred = resp.json().get("target_sql", "")
        ok = sql_equivalent(pred, fc["gold_sql"], fc["target_dialect"])
        tag = "OK" if ok else "FAIL"

        result = {
            "case_id": fc["case_id"],
            "mode": fc["mode"],
            "pair": fc["pair"],
            "sql_ok": ok,
            "pred_sql": pred[:200],
            "time": datetime.now().isoformat(),
        }

        if ok:
            progress["improved"] += 1
        else:
            progress["still_fail"] += 1
            result["pred_full"] = pred

    except Exception as e:
        tag = "ERROR"
        progress["errors"] += 1
        result = {
            "case_id": fc["case_id"],
            "mode": fc["mode"],
            "sql_ok": False,
            "error": str(e)[:200],
            "time": datetime.now().isoformat(),
        }

    progress["completed"] = i
    progress["results"].append(result)

    # 每条完成后写入进度（原子写）
    tmp = str(PROGRESS_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    Path(tmp).replace(PROGRESS_FILE)

    rate = progress["improved"] / i * 100 if i > 0 else 0
    print(f"  [{i}/{total}] {fc['case_id']} ({fc['mode']}): {tag}  |  ok={progress['improved']}/{i} ({rate:.0f}%)", flush=True)
    time.sleep(3)

progress["finished"] = True
progress["finished_at"] = datetime.now().isoformat()
tmp = str(PROGRESS_FILE) + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(progress, f, ensure_ascii=False, indent=2)
Path(tmp).rename(PROGRESS_FILE)

print(f"\n{'='*50}")
print(f"DONE: {progress['improved']}/{total} improved ({progress['improved']/total*100:.1f}%)")
print(f"Still failing: {progress['still_fail']}, Errors: {progress['errors']}")
