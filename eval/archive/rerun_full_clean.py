"""全量重跑 Full 模式 84 cases，每 5 个展示中间结果。"""
import json, sys, os, time
sys.path.insert(0, '.')

CKPT = 'eval/results/per_case_all_fast.json'

with open(CKPT, encoding='utf-8') as f:
    data = json.load(f)

from eval.run_eval import load_dataset, _eval_one, summarize
from eval.migration_client import MigrationClient
cases = load_dataset('eval/datasets', 'all')
print(f'[rerun-full] Total cases: {len(cases)}', flush=True)

client = MigrationClient(cooldown=3)

def print_interim(done, total):
    full_rows = [data[cid]['full'] for cid in data if 'full' in data[cid]]
    if not full_rows:
        return
    s = summarize(full_rows)
    ok = sum(1 for r in full_rows if r.get('sql_ok'))
    print(f'{"="*60}', flush=True)
    print(f'[interim] {done}/{total} | Full: {ok}/{len(full_rows)} SQL={s["sql_repair_rate"]:.4f} Recall@5={s.get("recall@5","N/A")}', flush=True)
    # per-pair
    pairs = {}
    for r in full_rows:
        p = r.get('pair','?')
        pairs.setdefault(p, {'ok':0,'n':0})
        pairs[p]['n'] += 1
        pairs[p]['ok'] += int(r.get('sql_ok',False))
    for p, st in sorted(pairs.items()):
        rate = st['ok']/st['n']*100 if st['n'] else 0
        print(f'  {p}: {st["ok"]}/{st["n"]} = {rate:.1f}%', flush=True)
    print(f'{"="*60}', flush=True)

ok_count = 0
fail_count = 0
for i, c in enumerate(cases):
    cid = c['id']
    if cid in data and 'full' in data[cid]:
        continue  # 已有数据跳过
    try:
        r = _eval_one(c, 'full', client, None, fast=True)
        if cid not in data:
            data[cid] = {}
        data[cid]['full'] = r
        tag = 'OK' if r['sql_ok'] else 'FAIL'
        ok_count += int(r['sql_ok'])
        fail_count += int(not r['sql_ok'])
        err = f' [{r.get("error","")}]' if r.get('error') else ''
        print(f'  [{i+1}/{len(cases)}] {tag} {cid} ({c["pair"]}){err}', flush=True)
    except Exception as e:
        fail_count += 1
        if cid not in data:
            data[cid] = {}
        data[cid]['full'] = {'id':cid, 'pair':c['pair'], 'sql_ok':False, 'error':str(e)}
        print(f'  [{i+1}/{len(cases)}] ERROR {cid}: {e}', flush=True)

    # 原子保存
    tmp = CKPT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CKPT)

    if (i + 1) % 5 == 0:
        print_interim(i + 1, len(cases))

print(f'\n[rerun-full] Done: {ok_count} OK, {fail_count} FAIL', flush=True)
print_interim(len(cases), len(cases))
