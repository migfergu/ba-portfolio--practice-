# Re-runnability Check

Command: `uv run oews-pipeline rerun-check --source sample`  
Executed: 2026-10-11T05:29:08+00:00 UTC on a fresh database (`data\processed\rerun_check.db`).

The pipeline was run twice against identical inputs. Analytic tables use natural-key upserts with row-hash change detection, so the second run must insert and update nothing. Audit tables (`etl_run`, `source_file_log`, `rejected_record`) intentionally append one batch per run so each run's lineage and rejects stay traceable.

| table | after run 1 | after run 2 | expected |
|---|---|---|---|
| dim_occupation | 20 | 20 | unchanged |
| dim_industry | 10 | 10 | unchanged |
| dim_year | 5 | 5 | unchanged |
| occupation_exposure | 19 | 19 | unchanged |
| occupation_preparation | 20 | 20 | unchanged |
| fact_oews_estimate | 645 | 645 | unchanged |
| etl_run | 1 | 2 | +1 run batch |
| source_file_log | 7 | 14 | +1 run batch |
| rejected_record | 9 | 18 | +1 run batch |

Run 2 fact load: inserted **0**, updated **0**, unchanged **645**, stale keys **0**.  
Fact fingerprint (SHA-256 of keys + row hashes): run 1 `b5e3ec8b07ea2c44`, run 2 `b5e3ec8b07ea2c44`.  
Rejected records per run: {1: 9, 2: 9}.

| check | result |
|---|---|
| Analytic table row counts identical after run 2 | PASS |
| Run 2 inserted 0 facts | PASS |
| Run 2 updated 0 facts | PASS |
| Run 2 left every fact unchanged | PASS |
| Fact content fingerprint identical | PASS |
| Same number of records rejected in each run | PASS |
| Audit tables grew by exactly one run's batch | PASS |

**Overall: PASS**
