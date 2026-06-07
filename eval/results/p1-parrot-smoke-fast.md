# P1 PARROT Smoke-Fast Evaluation

- Dataset: weizhoudb/PARROT `parrot_diverse.json` converted through `eval.parrot_adapter`
- Sample: deterministic shortest 5 mysql->postgresql + 5 oracle->postgresql rows
- Retrieval: full
- Migration model: deepseek-v4-flash, thinking disabled
- Judge model: deepseek-v4-flash, thinking disabled
- Scope note: smoke-fast only; not full PARROT and not comparable to public AccEX/AccRES baselines

| Scope | n | SQL repair rate | Report accuracy | Recall@5 |
|---|---:|---:|---:|---:|
| Overall | 10 | 0.8 | 1.0 | N/A |
| mysql_postgresql | 5 | 0.6 | 1.0 | N/A |
| oracle_postgresql | 5 | 1.0 | 1.0 | N/A |

## SQL Failures / Mismatches
- parrot-mysql-postgresql-25145 (mysql->postgresql): `DO $$ DECLARE current_time timestamp := TIMESTAMP '2022-12-01 12:40:00'; END $$;`
- parrot-mysql-postgresql-22998 (mysql->postgresql): `SELECT TO_CHAR(CreationDate, 'FMHH24:MI:SS') FROM comments`

## Notes
- PARROT rows have no gold_context_ids in the adapter output, so Recall@5 is null for this smoke run.
- This run is real API traffic, but deliberately fast-profiled for smoke validation.
