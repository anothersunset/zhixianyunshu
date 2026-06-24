"""Phase 3 Step 3.1: 失败模式聚类器。

读取 checkpoint JSON + 数据集 JSONL → 按方言特征聚类失败模式 →
输出 failure_analysis.json（按 fail_rate DESC, fail_count DESC 排序）。

用法:
    python -m eval.failure_analyzer \
        --checkpoint eval/results/per_case_all_fast.json \
        --dataset eval/datasets \
        --out eval/results/failure_analysis.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 加载 kb_loader
_KB_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "kb"))
if _KB_ROOT not in sys.path:
    sys.path.insert(0, os.path.dirname(_KB_ROOT))

from kb.kb_loader import load_dialect_config


# ── 方言特征提取（Python 版 DialectFeatureScanner Phase 1）──

def extract_features(source_sql: str, pair: str) -> List[Dict[str, Any]]:
    """从 source SQL 中提取已注册的方言特征（仅 Phase 1 精确匹配）。"""
    if not source_sql or not pair:
        return []
    source_dialect = pair.split("->")[0].strip().lower()
    config = load_dialect_config(source_dialect)
    if not config:
        return []

    features = config.get("features", [])
    lower_sql = source_sql.lower()
    # 剥离注释和字符串字面量（简化版，只处理最常见情况）
    clean = _strip_comments_and_strings(lower_sql)

    found = []
    for feat in features:
        keyword = feat["keyword"].lower()
        if _matches(keyword, clean):
            found.append({
                "keyword": feat["keyword"],
                "mapping": feat["mapping"],
                "category": feat["category"],
                "is_recipe": feat.get("is_recipe", False),
            })
    return found


def _strip_comments_and_strings(sql: str) -> str:
    """简化版注释/字符串剥离（与 Java 版逻辑一致但用 Python 实现）。"""
    import re
    # 移除单行注释 --
    sql = re.sub(r'--[^\n]*', ' ', sql)
    # 移除多行注释 /* */
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    # 移除字符串字面量 '...'
    sql = re.sub(r"'[^']*'", ' ', sql)
    return sql


def _matches(keyword: str, lower_sql: str) -> bool:
    """关键词匹配（与 Java DialectFeatureScanner.matches() 保持一致）。"""
    import re
    if keyword == "(+)":
        return "(+)" in lower_sql
    if keyword == "`":
        return "`" in lower_sql
    if keyword == "from dual":
        return "from dual" in re.sub(r'\s+', ' ', lower_sql)
    if keyword == "character set":
        return "character set" in lower_sql
    if keyword == "on duplicate key":
        return "on duplicate key" in lower_sql
    if keyword == "connect by":
        return "connect by" in lower_sql
    if keyword == "start with":
        return "start with" in lower_sql
    if keyword == "merge into":
        return "merge into" in re.sub(r'\s+', ' ', lower_sql)
    if keyword.endswith("("):
        return keyword in lower_sql
    # 默认：单词边界匹配
    return bool(re.search(r'(?s).*\b' + re.escape(keyword) + r'\b.*', lower_sql))


# ── 加载数据集 ──

def load_dataset(dataset_dir: str) -> Dict[str, Dict[str, Any]]:
    """加载所有 jsonl 数据集，返回 case_id → case_data 的映射。"""
    import glob as _glob
    cases: Dict[str, Dict[str, Any]] = {}
    for f in sorted(_glob.glob(os.path.join(dataset_dir, "*.jsonl"))):
        with open(f, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    c = json.loads(line)
                    cases[c["id"]] = c
    return cases


# ── 聚类分析 ──

def cluster_failures(
    checkpoint: Dict[str, Dict[str, Dict[str, Any]]],
    dataset: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """按特征模式聚类失败 case，返回排序后的聚类列表。"""
    feature_total: Dict[str, int] = defaultdict(int)           # 总出现次数 (case×mode)
    feature_fails: Dict[str, int] = defaultdict(int)           # 失败次数
    feature_cases: Dict[str, List[Dict[str, Any]]] = defaultdict(list)  # 失败 case 详情
    feature_modes: Dict[str, set] = defaultdict(set)           # 哪些 mode 失败

    for case_id, modes in checkpoint.items():
        case_data = dataset.get(case_id)
        if not case_data:
            continue
        source_sql = case_data.get("source_sql", "")
        pair = case_data.get("pair", "")
        gold_sql = case_data.get("gold_target_sql", "")

        # 提取该 case 的方言特征（所有 mode 共享）
        features = extract_features(source_sql, pair)
        if not features:
            continue

        feature_kw_set = {f["keyword"].lower() for f in features}

        for mode_name, result in modes.items():
            # 统计每个特征的总出现次数（case × mode）
            for kw in feature_kw_set:
                feature_total[kw] = feature_total.get(kw, 0) + 1

            if not result.get("sql_ok", True):
                # 该 mode 在该 case 上失败 → 所有特征都计为相关失败
                for kw in feature_kw_set:
                    feature_fails[kw] = feature_fails.get(kw, 0) + 1
                    feature_modes[kw].add(mode_name)
                    # 记录失败详情（每个特征最多保留 10 个样本避免文件过大）
                    if len(feature_cases[kw]) < 10:
                        feature_cases[kw].append({
                            "case_id": case_id,
                            "mode": mode_name,
                            "pair": pair,
                            "source_sql": source_sql,
                            "gold_sql": gold_sql,
                            "pred_sql": result.get("pred_sql", ""),
                            "error": result.get("error"),
                        })

    # 构建聚类结果
    clusters = []
    for kw, fail_count in feature_fails.items():
        total = feature_total.get(kw, fail_count)
        fail_rate = fail_count / total if total > 0 else 0.0
        # 获取该特征的详细信息
        feat_detail = _find_feature_detail(kw)
        clusters.append({
            "keyword": kw,
            "mapping": feat_detail.get("mapping", kw),
            "category": feat_detail.get("category", "unknown"),
            "is_recipe": feat_detail.get("is_recipe", False),
            "total_appearances": total,
            "fail_count": fail_count,
            "fail_rate": round(fail_rate, 4),
            "failing_modes": sorted(feature_modes.get(kw, set())),
            "mode_count": len(feature_modes.get(kw, set())),
            "sample_cases": feature_cases.get(kw, [])[:5],  # 最多 5 个样本
        })

    # 按 fail_rate DESC, fail_count DESC 排序
    clusters.sort(key=lambda c: (-c["fail_rate"], -c["fail_count"]))

    return clusters


def _find_feature_detail(keyword: str) -> Dict[str, Any]:
    """在所有方言 YAML 中查找关键词的详细信息。"""
    for dialect in ["oracle", "mysql", "sqlserver"]:
        config = load_dialect_config(dialect)
        if not config:
            continue
        for feat in config.get("features", []):
            if feat["keyword"].lower() == keyword.lower():
                return feat
    return {}


# ── 摘要统计 ──

def summarize_clusters(clusters: List[Dict[str, Any]], all_modes: set) -> Dict[str, Any]:
    """生成聚类摘要统计。"""
    if not clusters:
        return {"n_clusters": 0}

    # 严重性分级
    critical = [c for c in clusters if c["fail_rate"] >= 0.8 and c["mode_count"] >= 3]
    severe = [c for c in clusters if c["fail_rate"] >= 0.5 and c not in critical]
    moderate = [c for c in clusters if c["fail_rate"] < 0.5]

    # 最需要关注的 3 个模式
    top_failures = clusters[:5]

    # 建议操作
    suggestions = []
    for c in critical:
        suggestions.append({
            "keyword": c["keyword"],
            "action": "recipe",
            "reason": f"fail_rate={c['fail_rate']:.0%}, {c['mode_count']} modes affected — generate full recipe with few-shot",
        })
    for c in severe[:5]:
        suggestions.append({
            "keyword": c["keyword"],
            "action": "kb_doc",
            "reason": f"fail_rate={c['fail_rate']:.0%} — supplement KB documentation",
        })

    return {
        "n_clusters": len(clusters),
        "n_critical": len(critical),
        "n_severe": len(severe),
        "n_moderate": len(moderate),
        "critical_clusters": [c["keyword"] for c in critical],
        "top_failures": [
            {"keyword": c["keyword"], "fail_rate": c["fail_rate"], "fail_count": c["fail_count"]}
            for c in top_failures
        ],
        "suggested_actions": suggestions,
        "all_modes": sorted(all_modes),
    }


# ── 主入口 ──

def main():
    ap = argparse.ArgumentParser(description="失败模式聚类分析")
    ap.add_argument("--checkpoint", default="eval/results/per_case_all_fast.json",
                    help="Checkpoint JSON 文件路径")
    ap.add_argument("--dataset", default="eval/datasets",
                    help="数据集目录")
    ap.add_argument("--out", default="eval/results/failure_analysis.json",
                    help="输出 JSON 文件路径")
    args = ap.parse_args()

    # 1. 加载数据
    print(f"[failure_analyzer] Loading checkpoint: {args.checkpoint}")
    with open(args.checkpoint, encoding="utf-8") as fh:
        checkpoint = json.load(fh)

    print(f"[failure_analyzer] Loading datasets from: {args.dataset}")
    dataset = load_dataset(args.dataset)
    print(f"  {len(dataset)} cases in dataset, {len(checkpoint)} cases in checkpoint")

    # 2. 聚类分析
    clusters = cluster_failures(checkpoint, dataset)

    # 3. 摘要
    all_modes = set()
    for case_modes in checkpoint.values():
        all_modes.update(case_modes.keys())

    summary = summarize_clusters(clusters, all_modes)

    # 4. 输出
    output = {
        "summary": summary,
        "clusters": clusters,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    print(f"[failure_analyzer] Written {len(clusters)} clusters to {args.out}")

    # 打印摘要
    print(f"\n{'='*60}")
    print(f"失败聚类摘要")
    print(f"{'='*60}")
    print(f"聚类总数: {summary['n_clusters']}")
    print(f"严重(critical): {summary['n_critical']} — fail_rate >= 0.8 且 >=3 modes")
    print(f"较重(severe):   {summary['n_severe']} — fail_rate >= 0.5")
    print(f"一般(moderate): {summary['n_moderate']}")
    print(f"\nTop 5 失败模式:")
    for i, tf in enumerate(summary["top_failures"], 1):
        print(f"  {i}. {tf['keyword']} — fail_rate={tf['fail_rate']:.1%}, fail_count={tf['fail_count']}")
    print(f"\n建议操作:")
    for s in summary["suggested_actions"]:
        print(f"  [{s['action']}] {s['keyword']}: {s['reason']}")


if __name__ == "__main__":
    main()
