"""同批次配对重跑 CRAG 和 Full，每个 case 连续执行两次（crag→full），
确保两者在同一时间窗口、同一后端状态下运行，消除时序误差。

用法：
  python eval/rerun_crag_full_paired.py            # 正常跑
  python eval/rerun_crag_full_paired.py --clear    # 先清空 crag/full 再跑
  python eval/rerun_crag_full_paired.py --resume   # 跳过已有双结果的 case
"""
from __future__ import annotations
import argparse, json, os, sys, time
sys.path.insert(0, '.')

CKPT = 'eval/results/per_case_all_fast.json'
MODES = ['crag', 'full']

# ── 加载 checkpoint ──
with open(CKPT, encoding='utf-8') as f:
    data = json.load(f)

# ── CLI ──
ap = argparse.ArgumentParser()
ap.add_argument('--clear', action='store_true', help='清空 crag/full 后全量重跑')
ap.add_argument('--resume', action='store_true', help='跳过已有双结果的 case（默认行为）')
args = ap.parse_args()

if args.clear:
    cleared = 0
    for cid in data:
        for m in MODES:
            if m in data[cid]:
                del data[cid][m]
                cleared += 1
    print(f'[paired] 已清空 {cleared} 条记录', flush=True)

from eval.run_eval import load_dataset, _eval_one, summarize
from eval.migration_client import MigrationClient

cases = load_dataset('eval/datasets', 'all')
print(f'[paired] Total cases: {len(cases)}', flush=True)

client = MigrationClient(cooldown=3)


def save():
    tmp = CKPT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CKPT)


def print_interim(done, total):
    rows_crag = [data[cid]['crag'] for cid in data if 'crag' in data[cid]]
    rows_full = [data[cid]['full'] for cid in data if 'full' in data[cid]]
    if not rows_crag and not rows_full:
        return
    sc = summarize(rows_crag) if rows_crag else {}
    sf = summarize(rows_full) if rows_full else {}
    ok_c = sum(1 for r in rows_crag if r.get('sql_ok'))
    ok_f = sum(1 for r in rows_full if r.get('sql_ok'))
    print(f'{"="*60}', flush=True)
    print(f'[interim] {done}/{total}', flush=True)
    print(f'  CRAG: {ok_c}/{len(rows_crag)} SQL={sc.get("sql_repair_rate","N/A")} '
          f'Recall@5={sc.get("recall@5","N/A")}', flush=True)
    print(f'  Full: {ok_f}/{len(rows_full)} SQL={sf.get("sql_repair_rate","N/A")} '
          f'Recall@5={sf.get("recall@5","N/A")}', flush=True)
    # pair-level breakdown
    pairs_c: dict = {}
    pairs_f: dict = {}
    for r in rows_crag:
        p = r.get('pair', '?')
        pairs_c.setdefault(p, {'ok': 0, 'n': 0})
        pairs_c[p]['n'] += 1
        pairs_c[p]['ok'] += int(r.get('sql_ok', False))
    for r in rows_full:
        p = r.get('pair', '?')
        pairs_f.setdefault(p, {'ok': 0, 'n': 0})
        pairs_f[p]['n'] += 1
        pairs_f[p]['ok'] += int(r.get('sql_ok', False))
    all_pairs = sorted(set(list(pairs_c) + list(pairs_f)))
    for p in all_pairs:
        sc2 = pairs_c.get(p, {'ok': 0, 'n': 0})
        sf2 = pairs_f.get(p, {'ok': 0, 'n': 0})
        rc = sc2['ok'] / sc2['n'] * 100 if sc2['n'] else 0
        rf = sf2['ok'] / sf2['n'] * 100 if sf2['n'] else 0
        print(f'  {p}: CRAG {sc2["ok"]}/{sc2["n"]}={rc:.0f}%  '
              f'Full {sf2["ok"]}/{sf2["n"]}={rf:.0f}%', flush=True)
    print(f'{"="*60}', flush=True)


# ── 主循环 ──
done = 0
for i, c in enumerate(cases):
    cid = c['id']
    if cid not in data:
        data[cid] = {}

    # 判断是否跳过：两个 mode 都已有结果
    has_crag = 'crag' in data[cid]
    has_full = 'full' in data[cid]
    if has_crag and has_full:
        done += 1
        continue  # 已完成，跳过

    # 逐 mode 配对跑（crag → full）
    for mode in MODES:
        if mode in data[cid]:
            continue  # 该 mode 已有结果，跳过
        try:
            r = _eval_one(c, mode, client, None, fast=True)
            data[cid][mode] = r
            tag = 'OK' if r['sql_ok'] else 'FAIL'
            err = f' [{r.get("error", "")[:80]}]' if r.get('error') else ''
            print(f'  [{i+1}/{len(cases)}] {mode.upper()} {tag} {cid} ({c["pair"]}){err}', flush=True)
        except Exception as e:
            data[cid][mode] = {'id': cid, 'pair': c['pair'], 'sql_ok': False, 'error': str(e)}
            print(f'  [{i+1}/{len(cases)}] {mode.upper()} ERROR {cid}: {e}', flush=True)

    save()
    done += 1

    if done % 5 == 0:
        print_interim(done, len(cases))

# 最终汇总
print(f'\n[paired] Done: {done} cases processed', flush=True)
print_interim(len(cases), len(cases))
