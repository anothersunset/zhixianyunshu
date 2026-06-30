"""只跑 oracle-pg 配对（CRAG + Full 并行），跳过已完成的。"""
from __future__ import annotations
import json, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, '.')

CKPT = 'eval/results/per_case_all_fast.json'
with open(CKPT, encoding='utf-8') as f:
    data = json.load(f)

from eval.run_eval import load_dataset, _eval_one, summarize
from eval.migration_client import MigrationClient

cases = load_dataset('eval/datasets', 'all')
oracle_pg_cases = [c for c in cases if c['pair'] == 'oracle->postgresql']
print(f'[oracle-pg] Total: {len(oracle_pg_cases)} cases', flush=True)

# 两个独立 client，并行跑跳过节流
client_crag = MigrationClient(cooldown=0)
client_full = MigrationClient(cooldown=0)

def save():
    tmp = CKPT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CKPT)

def print_interim(done, total):
    rows_crag = [data[cid]['crag'] for cid in data if cid.startswith('oracle-pg') and 'crag' in data[cid]]
    rows_full = [data[cid]['full'] for cid in data if cid.startswith('oracle-pg') and 'full' in data[cid]]
    ok_c = sum(1 for r in rows_crag if r.get('sql_ok'))
    ok_f = sum(1 for r in rows_full if r.get('sql_ok'))
    diffs = sum(1 for cid in data if cid.startswith('oracle-pg') and 'crag' in data[cid] and 'full' in data[cid]
                and data[cid]['crag'].get('sql_ok') != data[cid]['full'].get('sql_ok'))
    print(f'{"="*60}', flush=True)
    print(f'[interim] {done}/{total} | CRAG={ok_c}/{len(rows_crag)} Full={ok_f}/{len(rows_full)} diffs={diffs}', flush=True)
    print(f'{"="*60}', flush=True)

done = 0
for c in oracle_pg_cases:
    cid = c['id']
    if cid not in data:
        data[cid] = {}
    has_both = 'crag' in data[cid] and 'full' in data[cid]
    if has_both:
        done += 1
        continue

    # 并行跑 CRAG 和 Full
    futures = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for mode, cl in [('crag', client_crag), ('full', client_full)]:
            if mode not in data[cid]:
                futures[pool.submit(_eval_one, c, mode, cl, None, True, True)] = mode
        for f in as_completed(futures):
            mode = futures[f]
            try:
                r = f.result()
                data[cid][mode] = r
                tag = 'OK' if r['sql_ok'] else 'FAIL'
                err = f' [{r.get("error", "")[:80]}]' if r.get('error') else ''
                print(f'  [{done+1}/{len(oracle_pg_cases)}] {mode.upper()} {tag} {cid}{err}', flush=True)
            except Exception as e:
                data[cid][mode] = {'id': cid, 'pair': c['pair'], 'sql_ok': False, 'error': str(e)}
                print(f'  [{done+1}/{len(oracle_pg_cases)}] {mode.upper()} ERROR {cid}: {e}', flush=True)

    save()
    done += 1
    if done % 5 == 0:
        print_interim(done, len(oracle_pg_cases))

print(f'\n[oracle-pg] Done: {done}', flush=True)
print_interim(len(oracle_pg_cases), len(oracle_pg_cases))
