"""P1 评测主入口（单组）。

用法：
  python -m eval.run_eval --retrieval full --pair all --use-judge
  python -m eval.run_eval --retrieval bm25 --pair mysql_opengauss
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

from eval.judge import LLMJudge
from eval.metrics import recall_at_k, report_point_hit_rate, sql_equivalent
from eval.migration_client import MigrationClient

RETRIEVAL_CHOICES = ["bm25", "vector", "vector_rerank", "crag", "full"]


def _target_db(pair: str) -> str:
    # 'mysql->opengauss' / 'oracle->postgresql' -> 取箭头后的目标库。
    tail = pair.split("->")[-1] if "->" in pair else pair.split("_")[-1]
    return tail.strip()


def load_dataset(path: str, pair: str) -> list[dict]:
    if pair == "all":
        files = sorted(glob.glob(os.path.join(path, "*.jsonl")))
    else:
        files = [os.path.join(path, pair + ".jsonl")]
    cases: list[dict] = []
    for f in files:
        with open(f, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    cases.append(json.loads(line))
    return cases


def evaluate(cases, retrieval, client, judge=None):
    rows = []
    for c in cases:
        target = _target_db(c["pair"])
        try:
            res = client.run_migration(source_sql=c["source_sql"], pair=c["pair"], retrieval=retrieval)
            ok = sql_equivalent(res.target_sql, c["gold_target_sql"], target)
            if not ok and judge is not None:
                ok = judge.sql_semantically_equal(res.target_sql, c["gold_target_sql"], target)
            report_acc = report_point_hit_rate(res.report_points, c.get("gold_report_points", []), judge)
            recall = recall_at_k(res.retrieved_ids, c.get("gold_context_ids", []), k=5)
            if recall != recall:
                recall = None
            risk_level = res.risk_level
            pred_sql = res.target_sql
            error = None
        except Exception as exc:
            ok = False
            report_acc = 0.0 if c.get("gold_report_points") else 1.0
            recall = None
            risk_level = "error"
            pred_sql = ""
            error = str(exc)
        rows.append({
            "id": c["id"],
            "pair": c["pair"],
            "difficulty": c.get("difficulty"),
            "sql_ok": bool(ok),
            "report_acc": report_acc,
            "recall@5": recall,
            "risk_level": risk_level,
            "pred_sql": pred_sql,
            "error": error,
        })
    return rows


def summarize(rows):
    n = len(rows)
    if not n:
        return {"n": 0}
    sql_rate = sum(1 for r in rows if r["sql_ok"]) / n
    report_acc = sum(r["report_acc"] for r in rows) / n
    recs = [r["recall@5"] for r in rows if r["recall@5"] is not None]
    recall = sum(recs) / len(recs) if recs else None
    return {
        "n": n,
        "sql_repair_rate": round(sql_rate, 4),
        "report_accuracy": round(report_acc, 4),
        "recall@5": round(recall, 4) if recall is not None else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrieval", choices=RETRIEVAL_CHOICES, default="full")
    ap.add_argument("--pair", default="all")
    ap.add_argument("--dataset", default="eval/datasets")
    ap.add_argument("--use-judge", action="store_true")
    ap.add_argument("--out", default="eval/results")
    args = ap.parse_args()

    cases = load_dataset(args.dataset, args.pair)
    client = MigrationClient()
    judge = LLMJudge() if args.use_judge else None
    rows = evaluate(cases, args.retrieval, client, judge)
    summary = summarize(rows)

    Path(args.out).mkdir(parents=True, exist_ok=True)
    out_file = os.path.join(args.out, "raw_" + args.retrieval + "_" + args.pair + ".json")
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "rows": rows}, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
