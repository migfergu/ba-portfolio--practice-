# Assignment 4 Evidence Map

Each rubric requirement, and where to find the evidence.

## Database Design (30)

| Requirement | Evidence |
|---|---|
| Normalized schema (3NF) with justification | `docs/ERD.md`, section "Design decisions"; DDL in `src/oews_pipeline/schema.py` |
| Primary and foreign keys | Composite PK `(soc_code, naics_code, year)` on facts; FKs to all three dimensions and to `etl_run`; `PRAGMA foreign_keys = ON` plus a post-load `foreign_key_check` (`pipeline.py`) |
| Constraints | CHECK constraints on code formats (SOC `GLOB`, 6-char NAICS), ranges (employment ≥ 0, wages > 0, ratings in [0,1], Job Zone 1–5), and 0/1 flags (`schema.py`) |
| Indexing strategy | `docs/ERD.md`, section "Indexing strategy" |
| ERD matches the implemented schema | `docs/ERD.md` Mermaid diagram lists the same 9 tables and columns as `schema.py` |

## ETL Implementation (30)

| Requirement | Evidence |
|---|---|
| Extract for every source | `extract.py`: `extract_oews`, `extract_exposure`, `extract_job_zones` |
| Transform | `transform.py`: grain filter, BLS symbol parsing, NAICS padding, O*NET→SOC aggregation, exposure z-score, dimension build |
| Load | `load.py`: natural-key upserts, row-hash change detection, stale-key reporting |
| Error handling and logging | `cli.py` (console plus `logs/` file, exit codes 0/1/2); `pipeline.py` (single transaction with rollback, `etl_run.status = failed` with the error message); test `test_failed_run_is_recorded_and_db_left_intact` |
| One documented command | `uv run oews-pipeline run` (`docs/PIPELINE.md`) |
| Re-runnable without corruption | `docs/RERUN_CHECK.md` (PASS: run 2 inserted 0, updated 0, fingerprints identical); tests `test_second_run_is_idempotent` and `test_refresh_updates_only_changed_rows` |

## Data Quality (20)

| Requirement | Evidence |
|---|---|
| Validation framework with automated checks | `validate.py`: Pydantic record contracts (custom framework allowed by the rubric) plus duplicate rules in `transform.py` |
| Quality metrics reported | `docs/QUALITY_REPORT.md` and `reports/quality_report_run1.json`: row counts and reconciliation, missingness by year, duplicates, rejected counts, coverage, FK integrity |
| Bad records handled explicitly | Every failure goes to `rejected_record` with raw values and a reason code. The action for each reason code is in `DATA_DICTIONARY.md` and the quality report, section 3. Nothing is dropped silently: rows read = out-of-scope + rejected + valid, for every source |

## Documentation & Code Quality (20)

| Requirement | Evidence |
|---|---|
| ERD, data dictionary, pipeline docs | `docs/ERD.md`, `docs/DATA_DICTIONARY.md`, `docs/PIPELINE.md` |
| Restricted-data review path | `docs/DATA_ACCESS.md`, `data/sample/README.md`, `.gitignore` |
| Modular code with docstrings | `src/oews_pipeline/`: one module per stage; every module, class and function has a docstring |
| Setup instructions another student can follow | `README.md`, section "Assignment 4" |
| Tests | `tests/test_pipeline.py` (8 tests) |
| Meaningful commit history | `git log`: staged commits for config → schema → extract/transform/validate → load/CLI → sample → quality/tests → docs |
| AI use disclosure | `docs/AI_USE.md` (A4 section) |
