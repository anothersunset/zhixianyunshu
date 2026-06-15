"""重跑 Full 模式失败 case，每 5 个展示中间结果。"""
import json, sys, os, time
sys.path.insert(0, '.')

CKPT = 'eval/results/per_case_all_fast.json'

with open(CKPT, encoding='utf-8') as f:
    data = json.load(f)

fail_ids = [cid for cid, m in data.items() if 'full' in m and not m['full'].get('sql_ok')]
print(f'[rerun] Full failed: {len(fail_ids)} cases', flush=True)

from eval.run_eval import load_dataset, _eval_one, summarize
from eval.migration_client import MigrationClient
cases = load_dataset('eval/datasets', 'all')
case_map = {c['id']: c for c in cases}
client = MigrationClient(cooldown=3)

def print_interim(done, total):
    full_rows = [data[cid]['full'] for cid in data if 'full' in data[cid]]
    s = summarize(full_rows)
    ok = sum(1 for r in full_rows if r.get('sql_ok'))
    print(f'{"="*60}', flush=True)
    print(f'[interim] {done}/{total} rerun | Full total: {ok}/{len(full_rows)} SQL={s["sql_repair_rate"]:.4f} Recall@5={s.get("recall@5","N/A")}', flush=True)
    print(f'{"="*60}', flush=True)

ok_count = 0
fail_count = 0
for i, cid in enumerate(fail_ids):
    c = case_map.get(cid)
    if not c:
        print(f'  [{i+1}/{len(fail_ids)}] SKIP {cid}', flush=True)
        continue
    try:
        r = _eval_one(c, 'full', client, None, fast=True)
        data[cid]['full'] = r
        tag = 'OK' if r['sql_ok'] else 'FAIL'
        ok_count += int(r['sql_ok'])
        fail_count += int(not r['sql_ok'])
        err = f' [{r.get("error","")}]' if r.get('error') else ''
        print(f'  [{i+1}/{len(fail_ids)}] {tag} {cid} ({c["pair"]}){err}', flush=True)
    except Exception as e:
        fail_count += 1
        print(f'  [{i+1}/{len(fail_ids)}] ERROR {cid}: {e}', flush=True)

    # 原子保存
    tmp = CKPT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CKPT)

    if (i + 1) % 5 == 0:
        print_interim(i + 1, len(fail_ids))

print(f'\n[rerun] Done: {ok_count} OK, {fail_count} FAIL', flush=True)
print_interim(len(fail_ids), len(fail_ids))
