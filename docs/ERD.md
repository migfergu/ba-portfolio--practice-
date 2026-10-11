# Entity-Relationship Diagram

Star schema at the **detailed occupation × 4-digit industry × May reference year** grain, plus audit tables for lineage. GitHub renders the Mermaid block below; field-level definitions are in [DATA_DICTIONARY.md](DATA_DICTIONARY.md).

```mermaid
erDiagram
    dim_occupation ||--o{ fact_oews_estimate : "soc_code"
    dim_industry   ||--o{ fact_oews_estimate : "naics_code"
    dim_year       ||--o{ fact_oews_estimate : "year"
    dim_occupation ||--o| occupation_exposure : "soc_code (1:0..1)"
    dim_occupation ||--o| occupation_preparation : "soc_code (1:0..1)"
    etl_run        ||--o{ fact_oews_estimate : "first_loaded_run / last_changed_run"
    etl_run        ||--|{ source_file_log : "run_id"
    etl_run        ||--o{ rejected_record : "run_id"

    dim_occupation {
        TEXT soc_code PK "2018 SOC NN-NNNN"
        TEXT occ_title
        TEXT major_group "NN-0000"
        TEXT focal_role "analyst | clerk_contrast | NULL"
        TEXT soc_vintage
    }
    dim_industry {
        TEXT naics_code PK "6-char BLS code, e.g. 523100"
        TEXT naics_title
        TEXT industry_level "4-digit"
        TEXT naics_sector "first 2 digits"
    }
    dim_year {
        INTEGER year PK "May reference year"
        TEXT period "pre | post"
        INTEGER post "1 if year >= 2023"
        INTEGER post_delayed "1 if year >= 2024"
        TEXT reference_month
    }
    occupation_exposure {
        TEXT soc_code PK, FK
        REAL exposure_alpha "E1"
        REAL exposure_beta "E1 + 0.5 E2"
        REAL exposure_gamma "E1 + E2"
        REAL exposure_main "configured measure"
        REAL exposure_z "standardized, 1 SD = 1"
        TEXT measure
        INTEGER n_onet_codes
        TEXT source_version
    }
    occupation_preparation {
        TEXT soc_code PK, FK
        REAL job_zone_mean
        INTEGER job_zone_max
        INTEGER n_onet_codes
        TEXT onet_version
    }
    fact_oews_estimate {
        TEXT soc_code PK, FK
        TEXT naics_code PK, FK
        INTEGER year PK, FK
        INTEGER tot_emp "NULL if suppressed"
        REAL emp_prse
        REAL a_mean "NULL if suppressed or top-coded"
        REAL h_mean
        REAL mean_prse
        INTEGER emp_suppressed
        INTEGER wage_suppressed
        INTEGER wage_topcoded
        TEXT source_file
        TEXT row_hash "change detection"
        INTEGER first_loaded_run FK
        INTEGER last_changed_run FK
    }
    etl_run {
        INTEGER run_id PK
        TEXT started_at
        TEXT finished_at
        TEXT status
        TEXT source_mode
        INTEGER facts_inserted
        INTEGER facts_updated
        INTEGER facts_unchanged
        INTEGER rows_rejected
        TEXT error_message
    }
    source_file_log {
        INTEGER run_id PK, FK
        TEXT source_name PK
        TEXT file_name
        TEXT version
        TEXT sha256
        INTEGER size_bytes
        INTEGER rows_read
    }
    rejected_record {
        INTEGER reject_id PK
        INTEGER run_id FK
        TEXT source_name
        TEXT record_key
        TEXT reason_code
        TEXT detail
        TEXT raw_record "JSON of original values"
    }
```

## Design decisions

**Why this grain.** The A3 specification, log(Y_oit) = α_oi + δ_it + β(Exposure_o × Post_t) + ε, needs one observation per occupation *o*, industry *i*, and year *t*. The composite primary key `(soc_code, naics_code, year)` enforces exactly that, so a duplicate cell cannot enter the estimation sample.

**Normalization (3NF).**
- OEWS repeats the occupation title and industry title on every row. Those depend only on `soc_code` or `naics_code`, so they live in `dim_occupation` and `dim_industry`; the fact table holds only measures that depend on the full key.
- Exposure and Job Zone scores depend only on the occupation, not on industry or year, so they are separate occupation-level tables. They are kept apart from `dim_occupation` because they come from different sources with different versions, and some occupations lack a score (1 : 0..1).
- Period flags depend only on the year, so `post` and `post_delayed` sit in `dim_year`. Changing the treatment timing is a one-row edit, not a fact-table rewrite.

**Suppression is data, not error.** BLS symbols (`**`, `*`, `#`) become NULL plus a flag. Rows are kept so coverage and selection into suppression can be reported, and the estimation step decides its own sample.

**Lineage.** Every fact records the run that first loaded it and the run that last changed it. Every run logs each file's SHA-256 and row count. Every rejected row is stored with its raw values. Any number in a later table can be traced back to a file and a run.

**Analysis view.** `v_analysis_panel` joins the star schema into the modeling frame and adds `exposure_x_post`, `emp_model_ready`, and `wage_model_ready`. Assignment 5 reads this view instead of re-deriving joins.

## Indexing strategy

The database is small (one row per occupation × industry × year, about 100k–200k facts on real data). It is refreshed in batches and read mostly by panel queries. Indexes therefore target the three access patterns that matter and nothing more, because every extra index slows each upsert.

| Index | Columns | Serves |
|---|---|---|
| PK (automatic) `fact_oews_estimate` | `(soc_code, naics_code, year)` | Upsert conflict detection on every load; occupation lookups (left-most column); uniqueness of the panel cell |
| `ix_fact_year_naics` | `(year, naics_code)` | Industry-by-year slices: the δ_it fixed effects, per-year coverage and quality-report queries |
| `ix_fact_naics_soc` | `(naics_code, soc_code)` | Occupation-by-industry cells across years: the α_oi fixed effects and the balanced-cell check |
| `ix_reject_run` | `(run_id, reason_code)` | Per-run reject summaries in the quality report |
| PK on each dimension | `soc_code`, `naics_code`, `year` | All joins in `v_analysis_panel` |

Low-cardinality flags (`post`, `emp_suppressed`) are not indexed. They split rows roughly in half or less, so SQLite's planner would scan the table anyway. To verify plans, run `EXPLAIN QUERY PLAN` against `v_analysis_panel`.
