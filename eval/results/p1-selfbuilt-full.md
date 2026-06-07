# P1 Self-built Full Evaluation

- Dataset: selfbuilt 18 cases
- Retrieval: full
- Migration model: DeepSeek V4-Pro, thinking enabled, reasoning_effort=high
- Judge model: DeepSeek V4-Pro, thinking enabled, reasoning_effort=high

| Scope | n | SQL repair rate | Report accuracy | Recall@5 |
|---|---:|---:|---:|---:|
| Overall | 18 | 0.8889 | 0.8889 | 0.0 |
| mysql_opengauss | 6 | 1.0 | 0.9167 | 0.0 |
| mysql_postgres | 6 | 0.8333 | 0.9167 | 0.0 |
| oracle_pg | 6 | 0.8333 | 0.8333 | 0.0 |

## SQL Failures
- mysql-pg-003 (mysql->postgresql, medium): `CREATE TABLE u (id BIGSERIAL PRIMARY KEY, status TEXT CHECK (status IN ('on', 'off')));`
- oracle-pg-002 (oracle->postgresql, easy): `SELECT LOCALTIMESTAMP;`

## Report Coverage Below 1.0
- mysql-og-004 (mysql->opengauss): report_acc=0.5
- mysql-pg-003 (mysql->postgresql): report_acc=0.5
- oracle-pg-005 (oracle->postgresql): report_acc=0.5
- oracle-pg-006 (oracle->postgresql): report_acc=0.5

## Notes
- Recall@5 is 0.0 because service retrieved_ids currently use static og-spec ids that do not align with gold_context_ids; treat this as a retrieval ID alignment issue pending audit.
- This is a real LLM run, not a mock or demo seed run.
