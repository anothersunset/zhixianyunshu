"""只跑 full 模式，验证 GraphRAG 优化效果。"""
import json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval.run_eval import _eval_one, load_dataset, summarize
from eval.migration_client import MigrationClient

def main():
    client = MigrationClient(cooldown=10)
    cases = load_dataset('eval/datasets', 'all')

    # 支持命令行参数限制 case 数量
    max_cases = int(sys.argv[1]) if len(sys.argv) > 1 else len(cases)
    if max_cases < len(cases):
        cases = cases[:max_cases]
        print(f'Limited to first {max_cases} cases', flush=True)

    ckpt_file = Path('eval/results/per_case_full_opt.json').resolve()
    checkpoint = {}
    if ckpt_file.exists():
        checkpoint = json.load(open(ckpt_file, encoding='utf-8'))
        print(f'Loaded checkpoint: {len(checkpoint)} cases', flush=True)

    mode = 'full'
    total = len(cases)
    done = 0
    t_start = time.time()

    for ci, case in enumerate(cases):
        cid = case['id']
        case_results = checkpoint.get(cid, {})
        print(f'[{ci+1}/{total}] {cid}: running full...', flush=True)
        try:
            row = _eval_one(case, mode, client, None, True, skip_throttle=False)
            case_results[mode] = row
            tag = 'OK' if row.get('sql_ok') else 'FAIL'
            recall = row.get('recall@5', 0) or 0
            print(f'  full: {tag} (recall@5={recall:.4f})', flush=True)
        except Exception as e:
            case_results[mode] = {'id': cid, 'pair': case['pair'], 'sql_ok': False, 'error': str(e)}
            print(f'  full: ERROR {e}', flush=True)
        checkpoint[cid] = case_results
        tmp = str(ckpt_file) + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        import os; os.replace(tmp, str(ckpt_file))
        done += 1

    elapsed = time.time() - t_start
    print(f'\nDone: {done} cases in {elapsed/60:.1f} min', flush=True)
    rows = [checkpoint[cid].get(mode, {}) for cid in checkpoint if mode in checkpoint[cid]]
    s = summarize(rows)
    print(f'  full: n={s.get("n")}, SQL={s.get("sql_repair_rate")}, Recall={s.get("recall@5")}', flush=True)

if __name__ == '__main__':
    main()
