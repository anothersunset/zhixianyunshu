"""实时监控消融实验进度并分析结果质量。"""
import re
import time
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
# Try multiple possible log locations
_possible = [
    os.environ.get("ABLATION_LOG", ""),
    "/tmp/ablation.log",
    os.path.join(os.environ.get("TEMP", ""), "ablation.log"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "ablation.log"),
]
LOG_FILE = next((p for p in _possible if p and os.path.exists(p)), "/tmp/ablation.log")

def analyze():
    try:
        with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except FileNotFoundError:
        print("等待日志文件...")
        return

    # 提取结果行
    pattern = r'\[(\d+)/(\d+)\] (OK|FAIL) (\S+) \(([^)]+)\)(?: \[([^\]]*)\])?'
    matches = re.findall(pattern, content)

    if not matches:
        print("暂无结果...")
        return

    total_expected = int(matches[0][1])
    done = len(matches)
    ok = sum(1 for m in matches if m[2] == "OK")
    fail = sum(1 for m in matches if m[2] == "FAIL")

    # 按 pair 分组统计
    pair_stats = {}
    fail_reasons = []
    for m in matches:
        idx, total, status, case_id, pair, reason = m
        if pair not in pair_stats:
            pair_stats[pair] = {"ok": 0, "fail": 0, "total": 0}
        pair_stats[pair]["total"] += 1
        if status == "OK":
            pair_stats[pair]["ok"] += 1
        else:
            pair_stats[pair]["fail"] += 1
            if reason:
                fail_reasons.append((case_id, pair, reason))

    # 按难度分组（从case_id推测）
    print("=" * 60)
    print(f"  消融实验实时监控 (更新于 {time.strftime('%H:%M:%S')})")
    print("=" * 60)
    print()

    # 当前模式
    mode_match = re.search(r'\[(\d)/5\] ([^:]+):', content)
    if mode_match:
        print(f"  当前模式: [{mode_match.group(1)}/5] {mode_match.group(2)}")

    # 进度条
    pct = done / total_expected * 100
    bar_len = 40
    filled = int(bar_len * done / total_expected)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"  进度: [{bar}] {done}/{total_expected} ({pct:.1f}%)")
    print()

    # 成功率
    rate = ok / done * 100 if done else 0
    print(f"  SQL 修复率: {ok}/{done} = {rate:.1f}%")
    print()

    # 按 pair 细分
    print("  按迁移对细分:")
    print(f"  {'迁移对':<25} {'通过':>6} {'失败':>6} {'成功率':>8}")
    print("  " + "-" * 50)
    for pair, stats in sorted(pair_stats.items()):
        r = stats["ok"] / stats["total"] * 100 if stats["total"] else 0
        print(f"  {pair:<25} {stats['ok']:>6} {stats['fail']:>6} {r:>7.1f}%")
    print()

    # 最近失败的 case
    if fail_reasons:
        print("  最近失败用例 (最多显示 5 条):")
        for cid, pair, reason in fail_reasons[-5:]:
            print(f"    {cid} ({pair}): {reason[:60]}")
        print()

    # 估计剩余时间（每个 case ~30 秒）
    remaining = total_expected - done
    est_seconds = remaining * 30
    est_min = est_seconds // 60
    print(f"  预计剩余: ~{est_min} 分钟 ({remaining} 个 case)")

    # 写入结果文件提示
    print()
    print("  结果文件: eval/results/raw_bm25_all.json")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        while True:
            analyze()
            time.sleep(15)
    else:
        analyze()
