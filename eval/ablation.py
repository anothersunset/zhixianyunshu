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


def run_all(dataset="eval/datasets", pair="all", use_judge=True):
    client = MigrationClient()
    judge = LLMJudge() if use_judge else None
    cases = load_dataset(dataset, pair)
    table = {}
    for r in RETRIEVAL_CHOICES:
        rows = evaluate(cases, r, client, judge)
        table[r] = {"summary": summarize(rows), "rows": rows}
    return table


def to_markdown(table) -> str:
    head = "| 组别 | Recall@5 | SQL 修复成功率 | 迁移报告准确率 | n |"
    sep = "|---|---|---|---|---|"
    lines = [head, sep]
    for r in RETRIEVAL_CHOICES:
        s = table[r]["summary"]
        lines.append("| {0} | {1} | {2} | {3} | {4} |".format(
            GROUP_LABEL[r],
            s.get("recall@5"),
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
    args = ap.parse_args()

    table = run_all(args.dataset, args.pair, args.use_judge)
    md = to_markdown(table)
    Path("eval/results").mkdir(parents=True, exist_ok=True)
    with open("eval/results/p1-ablation.md", "w", encoding="utf-8") as fh:
        fh.write(md + "\n")
    with open("eval/results/p1-ablation.json", "w", encoding="utf-8") as fh:
        json.dump({k: v["summary"] for k, v in table.items()}, fh, ensure_ascii=False, indent=2)
    print(md)


if __name__ == "__main__":
    main()
