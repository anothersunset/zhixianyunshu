"""零假设/安慰剂基线（A/A test）：量化"同一套配置跑两次，纯粹因采样噪声能差多少"。

用途：消融报告说"CRAG 比 BM25 高 8 个百分点"——这 8% 是真信号还是噪声？没有对照组
你回答不了这个问题。做法：把同一个 mode 在同一批 case 上完整跑两次（不同时间、独立
LLM 调用，产生两份 raw_*.json），拿两次结果喂给 compare_runs()，得到的差异就是
"什么都没变、纯噪声"能造成的幅度——你的 A/B 差异必须显著超过这个噪声地板，才配被
称为"梯度"。

用法：
    python -m eval.run_eval --retrieval full --pair mysql_opengauss --out eval/results/aa_run1
    python -m eval.run_eval --retrieval full --pair mysql_opengauss --out eval/results/aa_run2
    python -m eval.noise_floor --a eval/results/aa_run1/raw_full_mysql_opengauss.json \\
                                --b eval/results/aa_run2/raw_full_mysql_opengauss.json
"""
from __future__ import annotations

import argparse
import json


def compare_runs(rows_a: list[dict], rows_b: list[dict],
                  metric_keys: tuple[str, ...] = ("recall@5", "mrr@10")) -> dict:
    """按 id 匹配两组结果，返回噪声地板统计。两组理论上应是同一 mode 跑两次的产出。"""
    by_id_a = {r["id"]: r for r in rows_a if "id" in r}
    by_id_b = {r["id"]: r for r in rows_b if "id" in r}
    common_ids = sorted(set(by_id_a) & set(by_id_b))
    if not common_ids:
        return {"n": 0, "error": "no common case ids between the two runs"}

    result: dict = {"n": len(common_ids)}

    # sql_ok 是二元指标：flip_rate（个案层面翻转率）+ rate_delta（汇总层面噪声地板）
    a_ok = [bool(by_id_a[cid].get("sql_ok")) for cid in common_ids]
    b_ok = [bool(by_id_b[cid].get("sql_ok")) for cid in common_ids]
    flips = sum(1 for x, y in zip(a_ok, b_ok) if x != y)
    rate_a = sum(1 for x in a_ok if x) / len(a_ok)
    rate_b = sum(1 for x in b_ok if x) / len(b_ok)
    result["sql_ok"] = {
        "flip_rate": round(flips / len(common_ids), 4),
        "rate_a": round(rate_a, 4),
        "rate_b": round(rate_b, 4),
        "rate_delta": round(abs(rate_a - rate_b), 4),
    }

    # 连续指标：逐 case 绝对差的均值 + 汇总均值之差
    for key in metric_keys:
        pairs = [(by_id_a[cid].get(key), by_id_b[cid].get(key)) for cid in common_ids]
        pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
        if not pairs:
            result[key] = {"n": 0}
            continue
        mean_abs_diff = sum(abs(x - y) for x, y in pairs) / len(pairs)
        mean_a = sum(x for x, _ in pairs) / len(pairs)
        mean_b = sum(y for _, y in pairs) / len(pairs)
        result[key] = {
            "n": len(pairs),
            "mean_abs_diff": round(mean_abs_diff, 4),
            "mean_a": round(mean_a, 4),
            "mean_b": round(mean_b, 4),
            "mean_delta": round(abs(mean_a - mean_b), 4),
        }
    return result


def format_report(stats: dict) -> str:
    if stats.get("n") == 0:
        return f"无法比较：{stats.get('error', '两份结果没有共同的 case id')}"
    lines = [f"噪声基线对比（n={stats['n']} 个共同 case）", "-" * 50]
    s = stats.get("sql_ok")
    if s:
        lines.append(
            f"sql_ok: flip_rate={s['flip_rate']:.2%}  "
            f"rate_a={s['rate_a']:.2%} rate_b={s['rate_b']:.2%}  "
            f"rate_delta(噪声地板)={s['rate_delta']:.2%}"
        )
    for key, v in stats.items():
        if key in ("n", "sql_ok") or not isinstance(v, dict) or "mean_abs_diff" not in v:
            continue
        lines.append(
            f"{key}: mean_abs_diff={v['mean_abs_diff']:.4f}  "
            f"mean_delta(噪声地板)={v['mean_delta']:.4f}  (n={v['n']})"
        )
    lines.append("")
    lines.append(
        "解读：以上都是同一配置跑两次产生的差异。你的 A/B 实验差异应显著大于这里的\n"
        "rate_delta / mean_delta；如果同一量级，那个\"梯度\"更可能是噪声，不该拿来下结论。"
    )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="A/A 噪声基线：比较同一 mode 独立跑两次的结果，量化纯噪声能造成多大差异。"
    )
    ap.add_argument("--a", required=True, help="第一次跑的 raw_*.json 结果文件")
    ap.add_argument("--b", required=True, help="同一 mode 第二次跑的 raw_*.json 结果文件")
    ap.add_argument("--metrics", default="recall@5,mrr@10",
                    help="逗号分隔的连续型指标名（默认 recall@5,mrr@10）")
    args = ap.parse_args()

    with open(args.a, encoding="utf-8") as fh:
        rows_a = json.load(fh)["rows"]
    with open(args.b, encoding="utf-8") as fh:
        rows_b = json.load(fh)["rows"]

    metric_keys = tuple(m.strip() for m in args.metrics.split(",") if m.strip())
    stats = compare_runs(rows_a, rows_b, metric_keys)
    print(format_report(stats))


if __name__ == "__main__":
    main()
