"""消融：跑全部 5 组检索配置并汇总成对比表。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.judge import LLMJudge
from eval.migration_client import MigrationClient
from eval.run_eval import RETRIEVAL_CHOICES, evaluate, load_dataset, summarize

GROUP_LABEL = {
    "bm25": "A · BM25 only",
    "vector": "B · Vector only",
    "vector_rerank": "C · Vector + Rerank",
    "crag": "D · + CRAG",
    "full": "E · + GraphRAG / CKG",
}


def run_all(dataset="eval/datasets", pair="all", use_judge=True, fast=False, parallel=1):
    client = MigrationClient()
    judge = LLMJudge() if use_judge else None
    cases = load_dataset(dataset, pair)
    table = {}
    for r in RETRIEVAL_CHOICES:
        rows = evaluate(cases, r, client, judge, fast=fast, parallel=parallel)
        table[r] = {"summary": summarize(rows), "rows": rows}
    return table


def to_markdown(table) -> str:
    head = "| 组别 | Recall@5 | SQL 修复成功率 | 迁移报告准确率 | n |"
    sep = "|---|---|---|---|---|"
    lines = [head, sep]
    for r in RETRIEVAL_CHOICES:
        s = table[r]["summary"]
        rec = s.get("recall@5")
        rec_str = f"{rec:.4f}" if rec is not None else "N/A"
        lines.append("| {0} | {1} | {2} | {3} | {4} |".format(
            GROUP_LABEL[r],
            rec_str,
            s.get("sql_repair_rate"),
            s.get("report_accuracy"),
            s.get("n"),
        ))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="eval/datasets")
    ap.add_argument("--pair", default="all")
    ap.add_argument("--use-judge", action="store_true")
    ap.add_argument("--fast", action="store_true",
                    help="快速模式：跳过 AgentGraph，用 chat-model 模拟不同检索等级")
    ap.add_argument("--parallel", type=int, default=1)
    args = ap.parse_args()

    table = run_all(args.dataset, args.pair, args.use_judge, fast=args.fast, parallel=args.parallel)
    md = to_markdown(table)
    Path("eval/results").mkdir(parents=True, exist_ok=True)
    suffix = "_fast" if args.fast else ""
    with open(f"eval/results/p1-ablation{suffix}.md", "w", encoding="utf-8") as fh:
        fh.write(md + "\n")
    with open(f"eval/results/p1-ablation{suffix}.json", "w", encoding="utf-8") as fh:
        json.dump({k: v["summary"] for k, v in table.items()}, fh, ensure_ascii=False, indent=2)
    # 同时写出各 raw_*.json
    for r in RETRIEVAL_CHOICES:
        out_file = f"eval/results/raw_{r}_{args.pair}{suffix}.json"
        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(table[r], fh, ensure_ascii=False, indent=2)
    print(md)


if __name__ == "__main__":
    main()
