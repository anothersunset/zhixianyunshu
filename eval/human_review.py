"""人工抽检一致性：从已有结果中采样，产出人工标注模板，并计算 Cohen's Kappa。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.judge import cohen_kappa, sample_for_human_review


def load_rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("rows", data)


def load_dataset_map(dataset_dir: str) -> dict[str, dict]:
    """加载评测集 JSONL，返回 {case_id: case_dict}。"""
    import glob, os
    mapping = {}
    for f in sorted(glob.glob(os.path.join(dataset_dir, "*.jsonl"))):
        with open(f, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    c = json.loads(line)
                    mapping[c["id"]] = c
    return mapping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True, help="raw_*.json 结果文件路径")
    ap.add_argument("--labels", help="人工标注文件 (JSON list of 0/1 per sampled case)")
    ap.add_argument("--dataset", default="eval/datasets", help="评测集目录（用于补充 source_sql / gold_target_sql）")
    ap.add_argument("--ratio", type=float, default=0.33, help="采样比例")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rows = load_rows(args.result)
    samples = sample_for_human_review(rows, ratio=args.ratio, seed=args.seed)
    ds_map = load_dataset_map(args.dataset) if args.dataset else {}

    # 若无人工标注，输出待标注模板
    if not args.labels:
        template = []
        for s in samples:
            orig = ds_map.get(s["id"], {})
            template.append({
                "id": s["id"],
                "pair": s["pair"],
                "source_sql": orig.get("source_sql", ""),
                "gold_target_sql": orig.get("gold_target_sql", ""),
                "pred_sql": s.get("pred_sql", ""),
                "report_acc": s.get("report_acc"),
                "sql_ok": s.get("sql_ok"),
                "human_sql_ok": None,   # 0 或 1，SQL 是否正确
                "human_note": "",
            })
        out_file = str(Path(args.result).with_suffix("")) + "_review_template.json"
        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(template, fh, ensure_ascii=False, indent=2)
        print(f"已生成 {len(template)} 条人工审核样本 → {out_file}")
        print("请填写 human_sql_ok (0/1) 和 human_note 后重新运行:")
        print(f"  python -m eval.human_review --result {args.result} --labels {out_file}")
        return

    # 有人工标注，计算 Kappa
    with open(args.labels, encoding="utf-8") as fh:
        human_data = json.load(fh)

    judge_labels = []
    human_labels = []
    mismatches = []
    for h in human_data:
        if h.get("human_sql_ok") is None:
            continue
        # 在 samples 中找到对应的 judge 判定
        match = next((s for s in samples if s["id"] == h["id"]), None)
        if match is None:
            continue
        jl = 1 if match.get("sql_ok") else 0
        hl = int(h["human_sql_ok"])
        judge_labels.append(jl)
        human_labels.append(hl)
        if jl != hl:
            mismatches.append({"id": h["id"], "judge": jl, "human": hl, "pred_sql": match.get("pred_sql", "")})

    if not judge_labels:
        print("ERROR: 无有效标注数据")
        sys.exit(1)

    kappa = cohen_kappa(judge_labels, human_labels)
    agree = sum(1 for a, b in zip(judge_labels, human_labels) if a == b)
    print(f"样本数: {len(judge_labels)}")
    print(f"一致数: {agree}")
    print(f"一致率: {agree / len(judge_labels):.4f}")
    print(f"Cohen's Kappa: {kappa:.4f}")
    if mismatches:
        print(f"\n不一致 case ({len(mismatches)}):")
        for m in mismatches:
            print(f"  {m['id']}: judge={m['judge']}, human={m['human']}, sql={m['pred_sql'][:80]}")

    verdict = "PASS" if kappa >= 0.6 and agree / len(judge_labels) >= 0.8 else "FAIL"
    print(f"\n判定: {verdict} (要求 kappa≥0.6 且 一致率≥0.8)")


if __name__ == "__main__":
    main()
