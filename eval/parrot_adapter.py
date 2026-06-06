"""把 PARROT 原始用例转换成本项目 gold JSON 行格式。

支持两类输入：
1. 显式翻译对字段：source_sql / target_sql / source_dialect / target_dialect。
2. Hugging Face PARROT 宽表字段：mysql / oracle / postgres 等多方言列。

默认从宽表中抽取 mysql->postgresql 与 oracle->postgresql，作为本项目
PARROT 第一层主力对标子集。输出到 eval/datasets/parrot/*.jsonl 后，
run_eval / ablation 无需改动即可直接跑。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
from typing import Iterable

DIALECT_ALIAS = {
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "pg": "postgresql",
    "mysql": "mysql",
    "oracle": "oracle",
    "opengauss": "opengauss",
}

DEFAULT_WIDE_PAIRS = [("mysql", "postgres"), ("oracle", "postgres")]
NULLISH = {None, "", "null", "None", "nan", "NaN"}


def _pick(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] not in NULLISH:
            return d[k]
    return default


def _norm_dialect(x: str) -> str:
    return DIALECT_ALIAS.get((x or "").strip().lower(), (x or "").strip().lower())


def _has_sql(value) -> bool:
    return value not in NULLISH and str(value).strip().lower() not in NULLISH


def convert_pair_case(raw: dict, idx: int) -> dict | None:
    src = _pick(raw, "source_sql", "src_sql", "input_sql", "source")
    gold = _pick(raw, "target_sql", "gold_sql", "tgt_sql", "output_sql", "gold")
    src_d = _norm_dialect(_pick(raw, "source_dialect", "src_dialect", "from", default=""))
    tgt_d = _norm_dialect(_pick(raw, "target_dialect", "tgt_dialect", "to", default=""))
    if not (src and gold and src_d and tgt_d):
        return None
    return {
        "id": str(_pick(raw, "id", default="parrot-{0}-{1}-{2:04d}".format(src_d, tgt_d, idx))),
        "pair": src_d + "->" + tgt_d,
        "difficulty": _pick(raw, "difficulty", default="unknown"),
        "category": "PARROT",
        "source_sql": src,
        "gold_target_sql": gold,
        "gold_report_points": _pick(raw, "report_points", default=[]),
        "gold_context_ids": [],
        "source_benchmark": "PARROT",
    }


def convert_wide_cases(raw: dict, idx: int, pairs: Iterable[tuple[str, str]]) -> list[dict]:
    cases: list[dict] = []
    row_id = str(_pick(raw, "id", default="{0:04d}".format(idx)))
    for src_col, tgt_col in pairs:
        src_sql = raw.get(src_col)
        gold_sql = raw.get(tgt_col)
        if not (_has_sql(src_sql) and _has_sql(gold_sql)):
            continue
        src_d = _norm_dialect(src_col)
        tgt_d = _norm_dialect(tgt_col)
        cases.append({
            "id": "parrot-{0}-{1}-{2:05d}".format(src_d, tgt_d, idx),
            "pair": src_d + "->" + tgt_d,
            "difficulty": _pick(raw, "difficulty", default="unknown"),
            "category": "PARROT",
            "source_sql": str(src_sql),
            "gold_target_sql": str(gold_sql),
            "gold_report_points": [],
            "gold_context_ids": [],
            "source_benchmark": "PARROT",
            "parrot_id": row_id,
            "parrot_dataset": _pick(raw, "benchmark", "dataset", default=None),
        })
    return cases


def _load_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "rows", "examples", "test"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    return []


def _load_jsonl(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_parquet(path: str) -> list[dict]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Reading parquet requires pandas/pyarrow. Install them or export PARROT to JSONL first.") from exc
    return pd.read_parquet(path).to_dict(orient="records")


def load_raw(src_dir: str) -> list[dict]:
    rows: list[dict] = []
    paths = sorted(glob.glob(os.path.join(src_dir, "**", "*.json"), recursive=True))
    paths += sorted(glob.glob(os.path.join(src_dir, "**", "*.jsonl"), recursive=True))
    paths += sorted(glob.glob(os.path.join(src_dir, "**", "*.parquet"), recursive=True))
    for path in paths:
        if path.endswith(".jsonl"):
            rows.extend(_load_jsonl(path))
        elif path.endswith(".parquet"):
            rows.extend(_load_parquet(path))
        else:
            rows.extend(_load_json(path))
    return rows


def parse_pairs(values: list[str]) -> list[tuple[str, str]]:
    if not values:
        return DEFAULT_WIDE_PAIRS
    pairs = []
    for value in values:
        if "->" not in value:
            raise ValueError("Pair must look like mysql->postgres, got: " + value)
        src, tgt = value.split("->", 1)
        pairs.append((src.strip().lower(), tgt.strip().lower()))
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="PARROT 数据集解压/导出后的根目录")
    ap.add_argument("--out", default="eval/datasets/parrot")
    ap.add_argument("--pair", action="append", default=[], help="宽表抽取方言对，如 mysql->postgres；可重复")
    args = ap.parse_args()

    raw = load_raw(args.src)
    wide_pairs = parse_pairs(args.pair)
    buckets: dict[str, list[dict]] = {}
    for i, r in enumerate(raw):
        case = convert_pair_case(r, i)
        cases = [case] if case is not None else convert_wide_cases(r, i, wide_pairs)
        for c in cases:
            pair_key = c["pair"].replace("->", "_")
            buckets.setdefault(pair_key, []).append(c)

    Path(args.out).mkdir(parents=True, exist_ok=True)
    total = 0
    for pair, cases in sorted(buckets.items()):
        out_file = os.path.join(args.out, pair + ".jsonl")
        with open(out_file, "w", encoding="utf-8") as fh:
            for c in cases:
                fh.write(json.dumps(c, ensure_ascii=False) + "\n")
        total += len(cases)
        print("{0}: {1} cases -> {2}".format(pair, len(cases), out_file))
    print("done, total", total)


if __name__ == "__main__":
    main()
