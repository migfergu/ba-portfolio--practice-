"""Load the Assignment 4 analysis panel and validate it before any analysis.

All analysis starts from the ``v_analysis_panel`` view created by ``oews_pipeline.schema``, so
the EDA never re-implements ETL logic. Derived variables (logs, exposure groups, event time)
are added here once and reused everywhere.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "data" / "processed" / "oews_genai.db"
REFERENCE_YEAR = 2022  # last pre-ChatGPT May reference year (A3 event-time reference)

# OEWS release facts (BLS technical notes for each May release; see docs/A5_RESEARCH_DESIGN.md).
# Each May estimate pools six semiannual survey panels collected over three years. A panel counts as
# post-ChatGPT when its reference month is after the 30 Nov 2022 release (May 2023 onward).
OEWS_VINTAGE = pd.DataFrame([
    # year, panels pooled, post-ChatGPT panels, estimation method, SOC, NAICS
    (2021, "Nov 2018 - May 2021", 0, "MB3 (first release)", "2018 SOC (first full)", "2017 NAICS"),
    (2022, "Nov 2019 - May 2022", 0, "MB3", "2018 SOC", "2022 NAICS"),
    (2023, "Nov 2020 - May 2023", 1, "MB3", "2018 SOC", "2022 NAICS"),
    (2024, "Nov 2021 - May 2024", 3, "MB3", "2018 SOC", "2022 NAICS"),
    (2025, "Nov 2022 - May 2025", 5, "MB3", "2018 SOC", "2022 NAICS"),
], columns=["year", "panels_pooled", "post_chatgpt_panels", "estimation", "soc", "naics"]).set_index("year")
OEWS_VINTAGE["post_panel_share"] = OEWS_VINTAGE["post_chatgpt_panels"] / 6

# One row of the analytical panel and where each field comes from (A4 feedback: row definition).
PANEL_DEFINITION = pd.DataFrame([
    ("Row (unit)", "occupation x 4-digit industry x May reference year", "BLS OEWS national industry-specific (nat4d)",
     "O_GROUP = detailed, I_GROUP = 4-digit; key (soc_code, naics_code, year)"),
    ("Outcome", "tot_emp -> log_emp", "OEWS TOT_EMP", "Employment level (a stock), not hires or separations"),
    ("Outcome", "a_mean -> log_wage", "OEWS A_MEAN", "Mean annual wage of incumbents; composition-sensitive"),
    ("Precision", "emp_prse, mean_prse", "OEWS EMP_PRSE, MEAN_PRSE", "Relative standard errors (%) for sensitivity checks"),
    ("Flags", "emp_suppressed, wage_suppressed, wage_topcoded", "OEWS symbols **, *, #", "Kept as NULL + flag, never imputed"),
    ("Exposure", "exposure_main / exposure_z", "Eloundou et al. (2024) occ_level.csv, dv_rating_gamma",
     "Predicted technical potential (E1+E2), fixed over time; NOT observed adoption"),
    ("Control / moderator", "job_zone_mean", "O*NET 27.0 Job Zones (Aug 2022, pre-ChatGPT)", "Preparation level 1-5"),
    ("Timing", "post (2023+), post_delayed (2024+)", "config/sources.toml", "Plus post_panel_share from OEWS_VINTAGE"),
], columns=["role", "field", "source", "notes"])

CROSSWALKS = pd.DataFrame([
    ("Exposure -> panel", "O*NET-SOC 8-digit (NN-NNNN.NN) -> 2018 SOC 6-digit", "Truncate suffix; mean of O*NET codes per SOC",
     "occupation_exposure.n_onet_codes"),
    ("Job Zones -> panel", "O*NET-SOC 8-digit -> 2018 SOC 6-digit", "Truncate suffix; mean and max per SOC",
     "occupation_preparation.n_onet_codes"),
    ("OEWS industries", "NAICS 4-digit, padded to 6 (5221 -> 522100)", "2017 NAICS (May 2021) vs 2022 NAICS (May 2022+)",
     "Changed 4-digit codes appear as unbalanced cells; add naics_crosswalk if found on raw load"),
    ("OEWS occupations", "2018 SOC detailed codes, all panel years", "No SOC crosswalk needed for May 2021-2025",
     "dim_occupation.soc_vintage"),
], columns=["join", "codes", "rule", "audit field"])

FOCAL_LABELS = {"analyst": "Financial & investment analysts (13-2051)",
                "clerk_contrast": "Bookkeeping/accounting clerks (43-3031)"}


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    """Open a read-only connection to the pipeline database.

    Args:
        db_path: Path to ``oews_genai.db``. Defaults to ``data/processed/oews_genai.db``.

    Returns:
        A ``sqlite3.Connection`` opened in read-only URI mode, so EDA cannot alter the database.

    Raises:
        FileNotFoundError: If the database has not been built yet (run ``uv run oews-pipeline run``).
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"{db_path} not found. Build it first: `uv run oews-pipeline run` "
            "(or `--source raw` for the real files).")
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def source_mode(conn: sqlite3.Connection) -> str:
    """Return 'sample' or 'raw' for the most recent successful ETL run (labels every output)."""
    row = conn.execute("SELECT source_mode FROM etl_run WHERE status = 'succeeded' "
                       "ORDER BY run_id DESC LIMIT 1").fetchone()
    return row[0] if row else "unknown"


def load_panel(db_path: Path | str = DEFAULT_DB) -> pd.DataFrame:
    """Load ``v_analysis_panel`` and add the derived variables used throughout the EDA.

    Added columns:
        log_emp, log_wage   natural logs of TOT_EMP and A_MEAN (A3 outcomes); NaN when suppressed
        event_time          year - 2022
        exposure_group      'High' / 'Low' exposure: occupation above / at-or-below the median
                            occupation exposure (median taken across occupations, not cells)
        exposure_tercile    'Low' / 'Middle' / 'High' occupation-level terciles
        cell_id             'soc|naics' identifier for an occupation x industry cell

    Args:
        db_path: Path to the pipeline database.

    Returns:
        One row per occupation x industry x year, with ``attrs['source_mode']`` set.
    """
    with connect(db_path) as conn:
        panel = pd.read_sql_query("SELECT * FROM v_analysis_panel", conn)
        mode = source_mode(conn)
    panel["log_emp"] = np.log(panel["tot_emp"].where(panel["tot_emp"] > 0))
    panel["log_wage"] = np.log(panel["a_mean"].where(panel["a_mean"] > 0))
    panel["event_time"] = panel["year"] - REFERENCE_YEAR
    panel["cell_id"] = panel["soc_code"] + "|" + panel["naics_code"]
    panel = add_exposure_groups(panel)
    panel.attrs["source_mode"] = mode
    return panel


def add_exposure_groups(panel: pd.DataFrame) -> pd.DataFrame:
    """Attach occupation-level exposure groups (median split and terciles).

    Groups are formed over *occupations* so that an occupation that appears in many industries
    does not move the cut-off. Occupations without an exposure score get NaN groups.
    """
    occ = panel.drop_duplicates("soc_code").dropna(subset=["exposure_main"])[["soc_code", "exposure_main"]]
    median = occ["exposure_main"].median()
    occ["exposure_group"] = np.where(occ["exposure_main"] > median, "High", "Low")
    occ["exposure_tercile"] = pd.qcut(occ["exposure_main"].rank(method="first"), 3,
                                      labels=["Low", "Middle", "High"]).astype(str)
    out = panel.drop(columns=[c for c in ("exposure_group", "exposure_tercile") if c in panel], errors="ignore")
    out = out.merge(occ[["soc_code", "exposure_group", "exposure_tercile"]], on="soc_code", how="left")
    out.attrs.update(panel.attrs)
    out.attrs["exposure_median"] = float(median)
    return out


@dataclass
class QualityCheck:
    """Result of :func:`validate_panel`: overall pass flag, per-check details and a summary table."""
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    details: dict[str, object] = field(default_factory=dict)
    coverage: pd.DataFrame | None = None


def validate_panel(panel: pd.DataFrame) -> QualityCheck:
    """Validate the panel before analysis (Assignment 5 step 1: 'validate data quality').

    Checks:
        unique_key        no duplicate natural key (soc_code, naics_code, year). OEWS rows are survey
                          estimates, not transactions, and carry no transaction ID: identical rows in a
                          source file are file-level repeats (handled at ETL), not duplicate events.
        years_complete    every configured year present
        flags_consistent  a suppressed value is NULL and a NULL value is flagged
        exposure_range    exposure_main within [0, 1]
        positive_values   employment and wages strictly positive where present
        exposure_coverage share of panel rows with an exposure score (reported, passes if >= 80%)

    Returns:
        :class:`QualityCheck` with a per-year coverage table (rows, model-ready, suppressed, top-coded).
    """
    checks, details = {}, {}
    dup = panel.duplicated(["soc_code", "naics_code", "year"]).sum()
    checks["unique_key"] = dup == 0
    details["duplicate_keys"] = int(dup)

    years = sorted(panel["year"].unique())
    checks["years_complete"] = years == list(range(min(years), max(years) + 1))
    details["years"] = [int(y) for y in years]

    emp_bad = ((panel["emp_suppressed"] == 1) & panel["tot_emp"].notna()).sum()
    wage_bad = ((panel["wage_suppressed"] == 1) & panel["a_mean"].notna()).sum()
    unflagged = (panel["tot_emp"].isna() & (panel["emp_suppressed"] == 0)).sum()
    checks["flags_consistent"] = (emp_bad + wage_bad) == 0
    details["flag_conflicts"] = int(emp_bad + wage_bad)
    details["emp_null_unflagged"] = int(unflagged)

    exp = panel["exposure_main"].dropna()
    checks["exposure_range"] = bool(exp.between(0, 1).all())
    checks["positive_values"] = bool((panel["tot_emp"].dropna() > 0).all() and (panel["a_mean"].dropna() > 0).all())

    share = panel["exposure_main"].notna().mean()
    checks["exposure_coverage"] = share >= 0.80
    details["exposure_coverage_share"] = round(float(share), 4)
    details["occupations_without_exposure"] = sorted(panel.loc[panel["exposure_main"].isna(), "soc_code"].unique())

    coverage = (panel.groupby("year")
                .agg(rows=("cell_id", "size"),
                     emp_model_ready=("emp_model_ready", "sum"),
                     wage_model_ready=("wage_model_ready", "sum"),
                     emp_suppressed=("emp_suppressed", "sum"),
                     wage_suppressed=("wage_suppressed", "sum"),
                     wage_topcoded=("wage_topcoded", "sum"),
                     employment_covered=("tot_emp", "sum"))
                .astype({"employment_covered": "int64"}))
    return QualityCheck(passed=all(checks.values()), checks=checks, details=details, coverage=coverage)


def balanced_cells(panel: pd.DataFrame, outcome: str = "log_emp") -> pd.DataFrame:
    """Return only cells observed (non-missing ``outcome``) in every panel year.

    Used for trend plots so that composition changes from suppression do not look like trends.
    """
    n_years = panel["year"].nunique()
    obs = panel.dropna(subset=[outcome]).groupby("cell_id")["year"].nunique()
    keep = obs[obs == n_years].index
    return panel[panel["cell_id"].isin(keep)].copy()


def panel_definition() -> pd.DataFrame:
    """What one row of the analytical panel is, and which source supplies each field."""
    return PANEL_DEFINITION.copy()


def oews_vintage() -> pd.DataFrame:
    """Per-year OEWS release facts: pooled panels, post-ChatGPT panel share, method, SOC/NAICS versions."""
    return OEWS_VINTAGE.copy()


def input_manifest(db_path: Path | str = DEFAULT_DB) -> pd.DataFrame:
    """Input files of the latest successful ETL run with SHA-256, size, rows and version.

    This is the reproducible run log the full-data verification relies on: an authorized reviewer
    rebuilds from their own licensed copies and compares these hashes, without data in git.
    """
    with connect(db_path) as conn:
        return pd.read_sql_query(
            """SELECT s.source_name, s.file_name, s.version, s.sha256, s.size_bytes, s.rows_read, r.run_id,
                      r.source_mode, r.finished_at
               FROM source_file_log s JOIN etl_run r ON r.run_id = s.run_id
               WHERE r.run_id = (SELECT MAX(run_id) FROM etl_run WHERE status = 'succeeded')
               ORDER BY s.source_name""", conn)


def attrition_table(panel: pd.DataFrame, db_path: Path | str = DEFAULT_DB) -> pd.DataFrame:
    """How many OEWS rows / cells survive each filter and merge, from source file to analysis sample.

    Stages: rows read -> out-of-grain aggregates filtered -> quarantined by validation -> facts loaded
    -> with exposure score -> employment reported -> employment model-ready -> cells with pre and post
    -> cells observed in every year (balanced). The last two are counted in cells, the rest in rows.
    """
    with connect(db_path) as conn:
        run = conn.execute("SELECT MAX(run_id) FROM etl_run WHERE status = 'succeeded'").fetchone()[0]
        read = conn.execute("SELECT COALESCE(SUM(rows_read),0) FROM source_file_log WHERE run_id = ? "
                            "AND source_name LIKE 'oews_%'", (run,)).fetchone()[0]
        rej = conn.execute("SELECT COUNT(*) FROM rejected_record WHERE run_id = ? AND source_name LIKE 'oews_%'",
                           (run,)).fetchone()[0]
    facts = len(panel)
    n_years = panel["year"].nunique()
    has_exp = panel["exposure_main"].notna()
    emp_rep = has_exp & panel["tot_emp"].notna()
    by_cell = panel[emp_rep].groupby("cell_id")
    pre_post = (by_cell["post"].nunique() == 2).sum()
    balanced = (by_cell["year"].nunique() == n_years).sum()
    rows = [
        ("OEWS rows read (5 files)", read, "rows"),
        ("In panel grain (detailed occ x 4-digit ind)", facts + rej, "rows"),
        ("Passed validation -> fact table", facts, "rows"),
        ("Occupation has an exposure score", int(has_exp.sum()), "rows"),
        ("Employment not suppressed (model-ready)", int(emp_rep.sum()), "rows"),
        ("Cells with >=1 pre and >=1 post year", int(pre_post), "cells"),
        ("Cells observed in all 5 years (balanced)", int(balanced), "cells"),
    ]
    out = pd.DataFrame(rows, columns=["stage", "n", "unit"])
    out.attrs["out_of_grain_filtered"] = int(read - rej - facts)
    out.attrs["quarantined"] = int(rej)
    out.attrs["cells_total"] = int(panel["cell_id"].nunique())
    return out


def compare_manifest(expected: list[dict], db_path: Path | str = DEFAULT_DB) -> pd.DataFrame:
    """Compare the database's input files against an expected run log (e.g. a committed eda_run_log.json).

    Args:
        expected: The ``inputs`` list from a run log: dicts with source_name, file_name, sha256, rows_read.
        db_path: Database built by the reviewer from their own licensed copies.

    Returns:
        One row per source with expected vs found SHA-256 and row counts and a ``match`` flag. A full
        match shows the reviewer reproduced the run on byte-identical inputs without any data being shared.
    """
    exp = pd.DataFrame(expected).set_index("source_name")
    got = input_manifest(db_path).set_index("source_name")
    out = exp[["file_name", "sha256", "rows_read"]].join(
        got[["file_name", "sha256", "rows_read"]], rsuffix="_found", how="outer")
    out["match"] = (out["sha256"] == out["sha256_found"]) & (out["rows_read"] == out["rows_read_found"])
    return out.reset_index()
