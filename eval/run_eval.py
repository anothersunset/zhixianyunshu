"""P1 评测主入口（单组）。

用法：
  python -m eval.run_eval --retrieval full --pair all --use-judge
  python -m eval.run_eval --retrieval bm25 --pair mysql_opengauss
  python -m eval.run_eval --retrieval full --pair mysql_opengauss --use-judge --fast --parallel 3
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from eval.judge import LLMJudge
from eval.metrics import recall_at_k, report_point_hit_rate, sql_equivalent
from eval.migration_client import MigrationClient

RETRIEVAL_CHOICES = ["bm25", "vector", "vector_rerank", "crag", "full"]


def _target_db(pair: str) -> str:
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


def _eval_one(c, retrieval, client, judge, fast, skip_throttle=False):
    """评估单个 case（供并行调用）。"""
    target = _target_db(c["pair"])
    try:
        res = client.run_migration(source_sql=c["source_sql"], pair=c["pair"], retrieval=retrieval, fast=fast, skip_throttle=skip_throttle)
        # 检测 LLM 解析失败（后端 parseFallback 返回 target_sql=""）
        parse_failed = not res.target_sql and res.risk_level == "high"
        if parse_failed:
            ok = False
            report_acc = 0.0
            recall = recall_at_k(res.retrieved_ids, c.get("gold_context_ids", []), k=5)
            if recall is not None and math.isnan(recall):
                recall = None
            risk_level = "parse_failed"
            pred_sql = ""
            error = "LLM returned non-JSON output"
        else:
            ok = sql_equivalent(res.target_sql, c["gold_target_sql"], target)
            if not ok and judge is not None:
                ok = judge.sql_semantically_equal(res.target_sql, c["gold_target_sql"], target)
            report_acc = report_point_hit_rate(res.report_points, c.get("gold_report_points", []), judge)
            recall = recall_at_k(res.retrieved_ids, c.get("gold_context_ids", []), k=5)
            if recall is not None and math.isnan(recall):
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
    return {
        "id": c["id"],
        "pair": c["pair"],
        "difficulty": c.get("difficulty"),
        "sql_ok": bool(ok),
        "report_acc": report_acc,
        "recall@5": recall,
        "risk_level": risk_level,
        "pred_sql": pred_sql,
        "error": error,
    }


def evaluate(cases, retrieval, client, judge=None, fast=False, parallel=1,
              on_progress=None, checkpoint_path=None, checkpoint_base_rows=None):
    """on_progress(done_rows): 每完成一批 case 后回调，用于增量保存 checkpoint。
    checkpoint_path: 直接写文件的路径（比 on_progress 回调更可靠）。
    checkpoint_base_rows: 断点续跑时已有的 rows，合并后写入 checkpoint。
    """
    import sys as _sys
    n = len(cases)
    base_rows = checkpoint_base_rows or []
    _ckpt_path = checkpoint_path  # local ref

    def _flush_checkpoint(current_rows):
        """直接写 checkpoint 文件（原子写入：先写 .tmp 再 rename，防崩溃丢文件）。"""
        all_rows = base_rows + current_rows
        if _ckpt_path:
            try:
                data = {"summary": summarize(all_rows), "rows": all_rows}
                tmp_path = _ckpt_path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
                os.replace(tmp_path, _ckpt_path)  # 原子替换
                print(f"  [ckpt] wrote {len(all_rows)} rows", flush=True)
                _sys.stdout.flush()
            except Exception as e:
                print(f"  [ckpt] WRITE ERROR: {e}", flush=True)
                _sys.stdout.flush()

    if parallel <= 1:
        rows = []
        for i, c in enumerate(cases):
            r = _eval_one(c, retrieval, client, judge, fast)
            rows.append(r)
            tag = "OK" if r["sql_ok"] else "FAIL"
            err_info = f" [{r['error'][:60]}]" if r.get("error") else ""
            print(f"  [{i+1}/{n}] {tag} {r['id']} ({r['pair']}){err_info}", flush=True)
            # 每个 case 完成后立即保存 checkpoint（防止崩溃丢数据）
            _flush_checkpoint(rows)
    else:
        rows = [None] * n
        done = 0
        with ThreadPoolExecutor(max_workers=parallel) as ex:
            futures = {ex.submit(_eval_one, c, retrieval, client, judge, fast): i for i, c in enumerate(cases)}
            for f in as_completed(futures):
                idx = futures[f]
                r = f.result()
                rows[idx] = r
                done += 1
                tag = "OK" if r["sql_ok"] else "FAIL"
                err_info = f" [{r['error'][:60]}]" if r.get("error") else ""
                print(f"  [{done}/{n}] {tag} {r['id']} ({r['pair']}){err_info}", flush=True)
                _flush_checkpoint([x for x in rows if x is not None])
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
    ap.add_argument("--fast", action="store_true",
                    help="跳过 AgentGraph，直接用 chat-model 单次生成（大幅加速 eval 迭代）")
    ap.add_argument("--parallel", type=int, default=1,
                    help="并行评估的并发数（默认 1 即串行）")
    ap.add_argument("--cooldown", type=float, default=None,
                    help="两次请求之间的最小间隔秒数（防后端过载，默认 3）")
    ap.add_argument("--out", default="eval/results")
    args = ap.parse_args()

    cases = load_dataset(args.dataset, args.pair)
    client = MigrationClient(cooldown=args.cooldown)
    judge = LLMJudge() if args.use_judge else None
    if args.fast:
        print(f"Fast mode: {len(cases)} cases, parallel={args.parallel}")
    rows = evaluate(cases, args.retrieval, client, judge, fast=args.fast, parallel=args.parallel)
    summary = summarize(rows)

    Path(args.out).mkdir(parents=True, exist_ok=True)
    suffix = "_fast" if args.fast else ""
    out_file = os.path.join(args.out, "raw_" + args.retrieval + "_" + args.pair + suffix + ".json")
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "rows": rows}, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
