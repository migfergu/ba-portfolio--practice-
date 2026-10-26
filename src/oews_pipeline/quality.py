"""Quality report: row reconciliation, missingness, duplicates, rejects + actions, coverage."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from .validate import REASON_ACTIONS

FACT_COLS = ["tot_emp", "emp_prse", "a_mean", "h_mean", "mean_prse"]


def _q(conn: sqlite3.Connection, sql: str, params=()) -> pd.DataFrame:
    """Run a query and return the result as a DataFrame."""
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return pd.DataFrame([tuple(r) for r in cur.fetchall()], columns=cols)


def build_report(conn: sqlite3.Connection, run_id: int, run_state: dict) -> dict:
    """Assemble every quality metric for one run into a dict (also saved as JSON)."""
    rep: dict = {"run_id": run_id, "source_mode": run_state["source_mode"],
                 "started_at": run_state["started_at"], "status": run_state.get("status", "succeeded")}

    rep["source_files"] = _q(conn, "SELECT source_name, file_name, substr(sha256,1,12) AS sha256_12, "
                                   "size_bytes, rows_read FROM source_file_log WHERE run_id = ? "
                                   "ORDER BY source_name", (run_id,)).to_dict("records")

    recon = []
    for src, st in run_state["source_stats"].items():
        rejected = sum(v for k, v in st.items() if k.startswith("rejected_"))
        oos = st.get("out_of_scope_filtered", 0)
        recon.append({"source": src, "rows_read": st["rows_read"], "out_of_scope_filtered": oos,
                      "rejected": rejected, "valid": st["rows_valid"],
                      "reconciles": st["rows_read"] == oos + rejected + st["rows_valid"]})
    rep["row_reconciliation"] = recon

    rj = _q(conn, "SELECT source_name, reason_code, COUNT(*) AS n FROM rejected_record WHERE run_id = ? "
                  "GROUP BY source_name, reason_code ORDER BY source_name, reason_code", (run_id,))
    rj["action_taken"] = rj["reason_code"].map(REASON_ACTIONS)
    rep["rejected_by_reason"] = rj.to_dict("records")
    rep["rejected_total"] = int(rj["n"].sum()) if len(rj) else 0

    rep["duplicates"] = {
        "source_exact_duplicates_quarantined": int(rj.loc[rj.reason_code == "DUPLICATE_EXACT", "n"].sum()),
        "source_conflicting_duplicates_quarantined": int(rj.loc[rj.reason_code == "DUPLICATE_CONFLICT", "n"].sum()),
        "database_duplicate_fact_keys": int(conn.execute(
            "SELECT COUNT(*) FROM (SELECT 1 FROM fact_oews_estimate GROUP BY soc_code, naics_code, year "
            "HAVING COUNT(*) > 1)").fetchone()[0]),
    }

    miss_sql = ", ".join(f"ROUND(100.0 * SUM({c} IS NULL) / COUNT(*), 2) AS {c}_pct_null" for c in FACT_COLS)
    rep["missingness_fact_by_year"] = _q(conn, f"SELECT year, COUNT(*) AS rows, {miss_sql}, "
                                               "SUM(emp_suppressed) AS emp_suppressed, SUM(wage_suppressed) AS wage_suppressed, "
                                               "SUM(wage_topcoded) AS wage_topcoded "
                                               "FROM fact_oews_estimate GROUP BY year ORDER BY year").to_dict("records")
    rep["missingness_dimensions"] = {
        "occupations_without_exposure": int(conn.execute(
            "SELECT COUNT(*) FROM dim_occupation o LEFT JOIN occupation_exposure e USING (soc_code) "
            "WHERE e.soc_code IS NULL").fetchone()[0]),
        "occupations_without_job_zone": int(conn.execute(
            "SELECT COUNT(*) FROM dim_occupation o LEFT JOIN occupation_preparation p USING (soc_code) "
            "WHERE p.soc_code IS NULL").fetchone()[0]),
    }

    rep["load_outcome"] = run_state["load_outcome"]

    cov = _q(conn, "SELECT year, COUNT(*) AS cells, SUM(tot_emp IS NOT NULL) AS emp_published, "
                   "SUM(a_mean IS NOT NULL) AS wage_published, SUM(exposure_z IS NOT NULL) AS exposure_matched, "
                   "SUM(emp_model_ready) AS emp_model_ready, SUM(wage_model_ready) AS wage_model_ready "
                   "FROM v_analysis_panel GROUP BY year ORDER BY year")
    rep["coverage_by_year"] = cov.to_dict("records")
    n_years = conn.execute("SELECT COUNT(*) FROM dim_year").fetchone()[0]
    rep["balanced_emp_cells"] = int(conn.execute(
        "SELECT COUNT(*) FROM (SELECT soc_code, naics_code FROM v_analysis_panel WHERE emp_model_ready = 1 "
        "GROUP BY soc_code, naics_code HAVING COUNT(DISTINCT year) = ?)", (n_years,)).fetchone()[0])
    rep["focal_occupation_cells"] = _q(conn, "SELECT focal_role, soc_code, COUNT(DISTINCT naics_code) AS industries, "
                                             "SUM(emp_model_ready) AS emp_model_ready_cells FROM v_analysis_panel "
                                             "WHERE focal_role IS NOT NULL GROUP BY focal_role, soc_code").to_dict("records")
    rep["foreign_key_violations"] = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    rep["table_counts"] = run_state["table_counts"]
    rep["exposure_merge"] = run_state["source_stats"].get("exposure", {})
    return rep


def _md_table(rows: list[dict]) -> str:
    """Render a list of dicts as a Markdown table."""
    if not rows:
        return "_none_\n"
    cols = list(rows[0].keys())
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join("" if r[c] is None else str(r[c]) for c in cols) + " |")
    return "\n".join(out) + "\n"


def write_report(rep: dict, json_dir: Path, md_path: Path) -> tuple[Path, Path]:
    """Write the JSON report to reports/ and the Markdown report to md_path."""
    json_dir.mkdir(parents=True, exist_ok=True)
    jpath = json_dir / f"quality_report_run{rep['run_id']}.json"
    jpath.write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")

    lo = rep["load_outcome"]
    dup = rep["duplicates"]
    em = rep["exposure_merge"]
    md = f"""# Data Quality Report

Generated by `uv run oews-pipeline run --source {rep['source_mode']}` (run {rep['run_id']}, started {rep['started_at']} UTC).
Machine-readable copy: `reports/{jpath.name}`.
{"" if rep['source_mode'] == "raw" else chr(10) + "> **Synthetic sample.** Counts below describe the committed synthetic files (with deliberately injected defects), not real BLS estimates." + chr(10)}
## 1. Source files

{_md_table(rep['source_files'])}
## 2. Row reconciliation (rows read = out-of-scope + rejected + valid)

Out-of-scope rows are BLS aggregate rows (all-occupation totals, major/minor/broad groups, non-4-digit industries). They are filtered by design, not errors.

{_md_table(rep['row_reconciliation'])}
## 3. Rejected records and action taken

Total quarantined this run: **{rep['rejected_total']}**. Every rejected row is stored in `rejected_record` with its raw values, reason code, and run id.

{_md_table(rep['rejected_by_reason'])}
## 4. Duplicates

What "duplicate" means here: OEWS rows are published survey **estimates**, one per occupation x industry x year, not transactions, and they carry no transaction identifier. An exact duplicate is therefore an identical *source row* repeated in a file (a file-level artifact), and a conflicting duplicate is two rows with the same natural key but different values. Neither establishes a duplicated underlying event; the checks only guarantee one estimate per key.

| check | count |
|---|---|
| Identical source rows: extra copies quarantined (one copy kept) | {dup['source_exact_duplicates_quarantined']} |
| Same natural key, different values: all copies quarantined | {dup['source_conflicting_duplicates_quarantined']} |
| Duplicate primary keys in `fact_oews_estimate` | {dup['database_duplicate_fact_keys']} |

## 5. Missingness

Fact table, % null by year. Nulls here are BLS suppression (`**`, `*`) or top-coding (`#`), retained with flags rather than dropped, so estimation can choose its own sample.

{_md_table(rep['missingness_fact_by_year'])}
Dimension gaps:

{_md_table([rep['missingness_dimensions']])}
## 6. Load outcome (idempotent upsert)

| inserted | updated | unchanged | stale keys kept |
|---|---|---|---|
| {lo['inserted']} | {lo['updated']} | {lo['unchanged']} | {lo['stale_keys_not_in_source']} |

## 7. Coverage: cells surviving suppression and merge

Exposure merge: {em.get('socs_after_aggregation', 'n/a')} SOCs after O*NET->SOC aggregation; {em.get('socs_not_in_oews_panel', 'n/a')} not in the OEWS panel (dropped); {em.get('panel_socs_without_exposure', 'n/a')} panel SOCs have no exposure score (kept, flagged not model-ready).

{_md_table(rep['coverage_by_year'])}
Balanced employment cells (model-ready in every year): **{rep['balanced_emp_cells']}**

Focal occupations:

{_md_table(rep['focal_occupation_cells'])}
## 8. Integrity

- Foreign-key violations (`PRAGMA foreign_key_check`): **{rep['foreign_key_violations']}**
- Table row counts after load:

{_md_table([rep['table_counts']])}"""
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")
    return jpath, md_path
