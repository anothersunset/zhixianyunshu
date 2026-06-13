"""Quick recall comparison: BM25 vs CRAG with reranker."""
import urllib.request, json

def retrieve(query, mode):
    body = json.dumps({'query': query, 'top_k': 5, 'mode': mode}).encode()
    req = urllib.request.Request('http://127.0.0.1:8004/retrieve', data=body,
                                headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return [it['id'] for it in data.get('items', [])]

tests = [
    ('mysql-og-001', 'select ifnull(col1, 0) from t1 mysql->opengauss', ['kb-func-ifnull']),
    ('mysql-og-019', 'select concat(first_name,chr(32),last_name) as full_name from emp mysql->opengauss', ['kb-func-concat']),
    ('mysql-og-020', 'create table t (id int auto_increment, d double, b bit(1)) mysql->opengauss', ['kb-type-autoincrement', 'kb-type-double', 'kb-type-bit']),
    ('mysql-pg-022', 'select * from t where match(col) against(abc) mysql->postgres', ['kb-syntax-fulltext']),
    ('mysql-pg-024', 'create table t (id int auto_increment, e enum(a,b), dt datetime) mysql->postgres', ['kb-type-autoincrement', 'kb-type-enum', 'kb-type-datetime']),
    ('oracle-pg-014', 'select months_between(d1, d2) from t oracle->postgres', ['kb-func-monthsbetween']),
    ('oracle-pg-020', 'select regexp_substr(col, pattern) from t oracle->postgres', ['kb-func-regexp_substr']),
    ('oracle-pg-028', 'select id, name from emp start with mgr is null connect by prior id = mgr oracle->postgres', ['kb-syntax-hierarchy']),
    ('oracle-pg-030', 'select sysdate, add_months(d, 1) from t where col(+) = val oracle->postgres', ['kb-join-outer', 'kb-func-sysdate', 'kb-func-addmonths']),
]

header = f"{'Case':<20} {'BM25':>6} {'CRAG':>6} {'Delta':>6}"
print(header)
print("-" * 50)
total_bm25 = total_crag = 0
n = 0
for case_id, query, gold in tests:
    bm25_ids = retrieve(query, 'bm25')[:5]
    crag_ids = retrieve(query, 'crag')[:5]
    bm25_recall = len(set(gold) & set(bm25_ids)) / len(gold) if gold else None
    crag_recall = len(set(gold) & set(crag_ids)) / len(gold) if gold else None
    if bm25_recall is not None:
        total_bm25 += bm25_recall
        total_crag += crag_recall
        n += 1
        delta = crag_recall - bm25_recall
        marker = " <<<" if delta < -0.01 else ""
        print(f"{case_id:<20} {bm25_recall:>6.3f} {crag_recall:>6.3f} {delta:>+6.3f}{marker}")
        if delta < -0.01:
            print(f"  BM25: {bm25_ids}")
            print(f"  CRAG: {crag_ids}")

print(f"\n{'Average':<20} {total_bm25/n:>6.3f} {total_crag/n:>6.3f} {(total_crag-total_bm25)/n:>+6.3f}")
