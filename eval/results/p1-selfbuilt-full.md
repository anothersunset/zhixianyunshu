# P1 Self-built Full Evaluation

- Dataset: selfbuilt 18 cases
- Retrieval: full
- Migration model: DeepSeek V4-Pro, thinking enabled, reasoning_effort=high
- Judge model: DeepSeek V4-Pro, thinking enabled, reasoning_effort=high
- Retriever: kb-hybrid-heuristic with gold-aligned kb-* evidence IDs

| Scope | n | SQL repair rate | Report accuracy | Recall@5 |
|---|---:|---:|---:|---:|
| Overall | 18 | 1.0 | 0.9167 | 1.0 |
| mysql_opengauss | 6 | 1.0 | 0.75 | 1.0 |
| mysql_postgres | 6 | 1.0 | 1.0 | 1.0 |
| oracle_pg | 6 | 1.0 | 1.0 | 1.0 |

## SQL Failures
- None

## Report Coverage Below 1.0
- mysql-og-001 (mysql->opengauss): report_acc=0.0
- mysql-og-004 (mysql->opengauss): report_acc=0.5

## Notes
- Recall@5 is computed after aligning service retrieved_ids to the self-built gold_context_ids namespace (`kb-*`).
- This is a real LLM run, not a mock or demo seed run.
