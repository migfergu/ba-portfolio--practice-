"""One-call EDA runner: every table, figure and test result, regenerated from the database.

``uv run oews-eda`` (or ``run_all()``) writes:
    reports/figures/fig01..fig11_*.png     stakeholder figures (300 dpi)
    reports/eda/*.csv                      descriptive, attrition and model tables
    reports/eda/eda_summary.json           headline numbers cited in docs/A5_EXECUTIVE_SUMMARY.md
    reports/eda/eda_run_log.json           reproducible run log: input SHA-256s, versions, code commit

Re-running after ``oews-pipeline run --source raw`` refreshes everything on the licensed data with
no code change; only aggregate outputs are written, so they are safe to commit.
"""
from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import seaborn

from . import __version__, data, describe, inference, plots

FIG_DIR = data.REPO_ROOT / "reports" / "figures"
TABLE_DIR = data.REPO_ROOT / "reports" / "eda"

LABELS = {"exposure_z": "GenAI exposure (+1 SD)", "job_zone_mean": "Job Zone (preparation, 1-5)",
          "pre_log_wage": "Pre-period log wage", "pre_log_emp": "Pre-period log employment",
          "exposure_main": "GenAI exposure", "d_log_emp": "Change in log employment",
          "d_log_wage": "Change in log wage"}

UNIVARIATE_COLS = ["tot_emp", "log_emp", "a_mean", "log_wage", "exposure_main", "job_zone_mean",
                   "emp_prse", "mean_prse"]
CORR_COLS = ["exposure_main", "job_zone_mean", "pre_log_wage", "pre_log_emp", "d_log_emp", "d_log_wage"]
MODEL_X = ["exposure_z", "job_zone_mean", "pre_log_wage"]
PRACTICAL_THRESHOLD = 0.01  # log points: ~1 percentage point of growth over the post period


def _git_commit() -> str:
    """Current commit hash of the repository, or 'unknown' outside git."""
    try:
        return subprocess.run(["git", "-C", str(data.REPO_ROOT), "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def run_log(db_path: Path | str = data.DEFAULT_DB) -> dict:
    """Reproducible run log: when, with what code and library versions, on which exact inputs.

    Contains only file names, versions, sizes, row counts and SHA-256 hashes, never source data, so it
    can be committed after a licensed-data run and compared against an authorized reviewer's rerun.
    """
    manifest = data.input_manifest(db_path)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_mode": manifest["source_mode"].iat[0] if len(manifest) else "unknown",
        "etl_run_id": int(manifest["run_id"].iat[0]) if len(manifest) else None,
        "code_commit": _git_commit(),
        "versions": {"oews_eda": __version__, "python": platform.python_version(), "pandas": pd.__version__,
                     "numpy": np.__version__, "scipy": scipy.__version__, "matplotlib": matplotlib.__version__,
                     "seaborn": seaborn.__version__},
        "inputs": manifest[["source_name", "file_name", "version", "sha256", "size_bytes", "rows_read"]]
        .to_dict(orient="records"),
    }


def run_all(db_path: Path | str = data.DEFAULT_DB, fig_dir: Path = FIG_DIR, table_dir: Path = TABLE_DIR,
            show: bool = False) -> dict:
    """Run the full EDA and write all outputs.

    Args:
        db_path: Pipeline database (sample or raw build).
        fig_dir: Folder for PNG figures.
        table_dir: Folder for CSV tables, the JSON summary and the run log.
        show: Keep figures open (for notebooks); otherwise close them after saving.

    Returns:
        Dict of the headline results (also written to ``eda_summary.json``).

    Raises:
        ValueError: If the data-quality gate fails; no statistics are produced on a bad panel.
    """
    fig_dir, table_dir = Path(fig_dir), Path(table_dir)
    table_dir.mkdir(parents=True, exist_ok=True)
    panel = data.load_panel(db_path)
    mode = panel.attrs["source_mode"]
    qc = data.validate_panel(panel)
    if not qc.passed:
        failed = [k for k, v in qc.checks.items() if not v]
        raise ValueError(f"Data-quality checks failed: {failed}. Fix the pipeline output before EDA.")

    # ---- design tables (row definition, vintages, crosswalks, attrition)
    attrition = data.attrition_table(panel, db_path)
    vintage = data.oews_vintage()
    data.panel_definition().to_csv(table_dir / "panel_definition.csv", index=False)
    vintage.to_csv(table_dir / "oews_vintage.csv")
    data.CROSSWALKS.to_csv(table_dir / "crosswalks.csv", index=False)
    attrition.to_csv(table_dir / "attrition.csv", index=False)
    qc.coverage.to_csv(table_dir / "coverage_by_year.csv")

    # ---- description
    cells = describe.cell_changes(panel)
    cells_delayed = describe.cell_changes(panel, post_col="post_delayed")
    occ = describe.occupation_table(panel)
    occ_emp = describe.occupation_changes(cells, "d_log_emp")
    occ_wage = describe.occupation_changes(cells, "d_log_wage")
    balanced = data.balanced_cells(panel, "log_emp")
    describe.univariate_summary(panel, UNIVARIATE_COLS).to_csv(table_dir / "univariate_panel.csv")
    occ.to_csv(table_dir / "occupation_profile.csv")
    corr = describe.correlation_table(cells, CORR_COLS)
    corr.to_csv(table_dir / "correlation_spearman.csv")

    # ---- inference: primary test is within industry (A3 comparison group)
    kw = {"practical_threshold": PRACTICAL_THRESHOLD}
    emp_test = inference.exposure_group_test(cells, "d_log_emp_wi", alternative="less", **kw)
    emp_test_raw = inference.exposure_group_test(cells, "d_log_emp", alternative="less", **kw)
    wage_test = inference.exposure_group_test(cells, "d_log_wage_wi", alternative="two-sided", **kw)
    emp_test_delayed = inference.exposure_group_test(cells_delayed, "d_log_emp_wi", alternative="less", **kw)
    pre = describe.pre_period_change(panel, "log_emp").merge(cells[["cell_id"]], on="cell_id")
    placebo = inference.exposure_group_test(pre, "d_pre_log_emp", alternative="two-sided", **kw)
    no2021 = describe.cell_changes(panel[panel["year"] != 2021])  # drops the 2017-NAICS release
    emp_test_no2021 = inference.exposure_group_test(no2021, "d_log_emp_wi", alternative="less", **kw)
    perm_emp = inference.occupation_permutation_test(occ_emp, y="d_log_emp", alternative="less")
    perm_wage = inference.occupation_permutation_test(occ_wage, y="d_log_wage", alternative="two-sided")

    m_emp = inference.ols_cluster(cells, "d_log_emp", MODEL_X, fixed_effects=["naics_code"])
    m_wage = inference.ols_cluster(cells, "d_log_wage", MODEL_X, fixed_effects=["naics_code"])
    m_emp.table.to_csv(table_dir / "model_emp_change.csv")
    m_wage.table.to_csv(table_dir / "model_wage_change.csv")
    vifs = inference.vif(cells, MODEL_X)

    gaps_emp = inference.event_time_gaps(describe.cell_year_changes(panel, "log_emp"))
    gaps_wage = inference.event_time_gaps(describe.cell_year_changes(panel, "log_wage"))
    gaps_emp.merge(vintage[["post_chatgpt_panels"]], left_on="year", right_index=True).to_csv(
        table_dir / "event_time_gaps_emp.csv", index=False)
    gaps_wage.to_csv(table_dir / "event_time_gaps_wage.csv", index=False)
    trend_emp = describe.trend_index(balanced, "exposure_tercile", "log_emp")
    contrast = describe.focal_contrast(panel)
    trend_emp.to_csv(table_dir / "trend_emp_by_tercile.csv", index=False)
    contrast.to_csv(table_dir / "focal_contrast.csv", index=False)

    tests = {"primary_emp_within_industry": emp_test, "emp_raw_change": emp_test_raw,
             "wage_within_industry": wage_test, "emp_delayed_post": emp_test_delayed,
             "emp_excluding_2021": emp_test_no2021, "placebo_2021_2022": placebo}
    pd.DataFrame({k: {"outcome": t.outcome, "H1": t.h1, "test": t.test_used, "p": t.p_value,
                      "gap_pct": t.diff_pct_points, "hedges_g": t.hedges_g,
                      "cluster_ci_low_pct": t.cluster_ci_low * 100, "cluster_ci_high_pct": t.cluster_ci_high * 100,
                      "decision": t.decision, "practical_verdict": t.practical_verdict}
                  for k, t in tests.items()}).T.to_csv(table_dir / "hypothesis_tests.csv")

    # ---- figures
    figs = [
        plots.plot_coverage(qc.coverage, fig_dir / "fig01_data_coverage.png", mode),
        plots.plot_exposure_distribution(occ, panel.attrs["exposure_median"],
                                         fig_dir / "fig02_exposure_distribution.png", mode),
        plots.plot_outcome_distributions(panel, fig_dir / "fig03_outcome_distributions.png", mode),
        plots.plot_exposure_vs_change(cells, occ_emp, "d_log_emp", fig_dir / "fig04_exposure_vs_emp_change.png", mode),
        plots.plot_trend_index(trend_emp, "Employment", fig_dir / "fig05_emp_trend_by_exposure.png", mode),
        plots.plot_correlation_heatmap(corr, LABELS, fig_dir / "fig06_correlation_heatmap.png", mode),
        plots.plot_coefficients(m_emp.table, LABELS, path=fig_dir / "fig07_model_coefficients.png", source_mode=mode),
        plots.plot_group_test(cells, "d_log_emp_wi", emp_test, fig_dir / "fig08_hypothesis_test_emp.png", mode),
        plots.plot_focal_contrast(contrast, fig_dir / "fig09_analyst_vs_clerk.png", mode),
        plots.plot_attrition(attrition, fig_dir / "fig10_merge_attrition.png", mode),
        plots.plot_event_time_gaps(gaps_emp, vintage, fig_dir / "fig11_event_time_gaps_emp.png", mode),
    ]
    if not show:
        for f in figs:
            plt.close(f)

    emp_g = describe.group_comparison(cells, "d_log_emp")
    wage_g = describe.group_comparison(cells, "d_log_wage")
    last = int(panel["year"].max())
    summary = {
        "source_mode": mode,
        "data_quality": {"passed": qc.passed, "checks": {k: bool(v) for k, v in qc.checks.items()},
                         **qc.details},
        "panel": {"rows": int(len(panel)), "cells": int(panel["cell_id"].nunique()),
                  "occupations": int(panel["soc_code"].nunique()), "industries": int(panel["naics_code"].nunique()),
                  "years": qc.details["years"], "balanced_emp_cells": int(balanced["cell_id"].nunique()),
                  "cells_with_change": int(cells["d_log_emp"].notna().sum())},
        "attrition": attrition.to_dict(orient="records"),
        "exposure_median": panel.attrs["exposure_median"],
        "practical_threshold_pct": PRACTICAL_THRESHOLD * 100,
        "group_means_pct": {"emp": emp_g["approx_pct_change"].round(2).to_dict(),
                            "wage": wage_g["approx_pct_change"].round(2).to_dict()},
        "tests": {k: t.to_dict() for k, t in tests.items()},
        "permutation_emp": perm_emp, "permutation_wage": perm_wage,
        "model_emp": {"formula": m_emp.formula, "n": m_emp.n_obs, "clusters": m_emp.n_clusters, "r2": m_emp.r2,
                      "coef": m_emp.table.round(5).to_dict(orient="index")},
        "model_wage": {"formula": m_wage.formula, "n": m_wage.n_obs, "clusters": m_wage.n_clusters, "r2": m_wage.r2,
                       "coef": m_wage.table.round(5).to_dict(orient="index")},
        "vif": vifs.round(2).to_dict(),
        "event_time_gaps_emp_pct": {int(r.year): round(r.gap * 100, 2) for r in gaps_emp.itertuples()},
        "event_time_gaps_wage_pct": {int(r.year): round(r.gap * 100, 2) for r in gaps_wage.itertuples()},
        f"emp_index_{last}_by_tercile": trend_emp[trend_emp["year"] == last].set_index("group")["index"]
        .round(1).to_dict(),
        f"focal_index_{last}": contrast[contrast["year"] == last].set_index("focal_role")[["emp_index", "wage_index"]]
        .round(1).to_dict(orient="index"),
    }
    (table_dir / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    (table_dir / "eda_run_log.json").write_text(json.dumps(run_log(db_path), indent=2, default=str))
    return summary
