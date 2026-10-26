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
        unique_key        no duplicate (soc_code, naics_code, year)
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
