"""One-call EDA runner: every table, figure and test result, regenerated from the database.

``uv run python -m oews_eda`` (or ``run_all()``) writes:
    reports/figures/fig01..fig09_*.png     stakeholder figures (300 dpi)
    reports/eda/*.csv                      descriptive and model tables
    reports/eda/eda_summary.json           headline numbers cited in docs/A5_EXECUTIVE_SUMMARY.md

Re-running after ``oews-pipeline run --source raw`` refreshes everything on the real data with
no code change.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

from . import data, describe, inference, plots

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


def run_all(db_path: Path | str = data.DEFAULT_DB, fig_dir: Path = FIG_DIR, table_dir: Path = TABLE_DIR,
            show: bool = False) -> dict:
    """Run the full EDA and write all outputs.

    Args:
        db_path: Pipeline database (sample or raw build).
        fig_dir: Folder for PNG figures.
        table_dir: Folder for CSV tables and the JSON summary.
        show: Keep figures open (for notebooks); otherwise close them after saving.

    Returns:
        Dict of the headline results (also written to ``eda_summary.json``).
    """
    fig_dir, table_dir = Path(fig_dir), Path(table_dir)
    table_dir.mkdir(parents=True, exist_ok=True)
    panel = data.load_panel(db_path)
    mode = panel.attrs["source_mode"]
    qc = data.validate_panel(panel)
    if not qc.passed:
        failed = [k for k, v in qc.checks.items() if not v]
        raise ValueError(f"Data-quality checks failed: {failed}. Fix the pipeline output before EDA.")

    cells = describe.cell_changes(panel)
    cells_delayed = describe.cell_changes(panel, post_col="post_delayed")
    occ = describe.occupation_table(panel)
    occ_emp = describe.occupation_changes(cells, "d_log_emp")
    occ_wage = describe.occupation_changes(cells, "d_log_wage")
    balanced = data.balanced_cells(panel, "log_emp")
    balanced_w = data.balanced_cells(panel, "log_wage")

    # ---- tables
    qc.coverage.to_csv(table_dir / "coverage_by_year.csv")
    describe.univariate_summary(panel, UNIVARIATE_COLS).to_csv(table_dir / "univariate_panel.csv")
    occ.to_csv(table_dir / "occupation_profile.csv")
    corr = describe.correlation_table(cells, CORR_COLS)
    corr.to_csv(table_dir / "correlation_spearman.csv")

    emp_test = inference.exposure_group_test(cells, "d_log_emp", alternative="less")
    wage_test = inference.exposure_group_test(cells, "d_log_wage", alternative="two-sided")
    emp_test_delayed = inference.exposure_group_test(cells_delayed, "d_log_emp", alternative="less")
    perm_emp = inference.occupation_permutation_test(occ_emp, y="d_log_emp", alternative="less")
    perm_wage = inference.occupation_permutation_test(occ_wage, y="d_log_wage", alternative="two-sided")

    m_emp = inference.ols_cluster(cells, "d_log_emp", MODEL_X, fixed_effects=["naics_code"])
    m_wage = inference.ols_cluster(cells, "d_log_wage", MODEL_X, fixed_effects=["naics_code"])
    m_emp.table.to_csv(table_dir / "model_emp_change.csv")
    m_wage.table.to_csv(table_dir / "model_wage_change.csv")
    vifs = inference.vif(cells, MODEL_X)

    trend_emp = describe.trend_index(balanced, "exposure_tercile", "log_emp")
    trend_wage = describe.trend_index(balanced_w, "exposure_tercile", "log_wage")
    contrast = describe.focal_contrast(panel)
    trend_emp.to_csv(table_dir / "trend_emp_by_tercile.csv", index=False)
    contrast.to_csv(table_dir / "focal_contrast.csv", index=False)

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
        plots.plot_group_test(cells, "d_log_emp", emp_test, fig_dir / "fig08_hypothesis_test_emp.png", mode),
        plots.plot_focal_contrast(contrast, fig_dir / "fig09_analyst_vs_clerk.png", mode),
    ]
    if not show:
        for f in figs:
            plt.close(f)

    emp_g = describe.group_comparison(cells, "d_log_emp")
    wage_g = describe.group_comparison(cells, "d_log_wage")
    last = int(panel["year"].max())
    tr = trend_emp[trend_emp["year"] == last].set_index("group")["index"].round(1).to_dict()
    cf = contrast[contrast["year"] == last].set_index("focal_role")[["emp_index", "wage_index"]].round(1)

    summary = {
        "source_mode": mode,
        "data_quality": {"passed": qc.passed, "checks": {k: bool(v) for k, v in qc.checks.items()},
                         **{k: v for k, v in qc.details.items()}},
        "panel": {"rows": int(len(panel)), "cells": int(panel["cell_id"].nunique()),
                  "occupations": int(panel["soc_code"].nunique()), "industries": int(panel["naics_code"].nunique()),
                  "years": qc.details["years"], "balanced_emp_cells": int(balanced["cell_id"].nunique()),
                  "cells_with_change": int(cells["d_log_emp"].notna().sum())},
        "exposure_median": panel.attrs["exposure_median"],
        "group_means_pct": {"emp": emp_g["approx_pct_change"].round(2).to_dict(),
                            "wage": wage_g["approx_pct_change"].round(2).to_dict()},
        "test_emp": emp_test.to_dict(), "test_wage": wage_test.to_dict(),
        "test_emp_delayed_post": emp_test_delayed.to_dict(),
        "permutation_emp": perm_emp, "permutation_wage": perm_wage,
        "model_emp": {"formula": m_emp.formula, "n": m_emp.n_obs, "clusters": m_emp.n_clusters, "r2": m_emp.r2,
                      "coef": m_emp.table.round(5).to_dict(orient="index")},
        "model_wage": {"formula": m_wage.formula, "n": m_wage.n_obs, "clusters": m_wage.n_clusters, "r2": m_wage.r2,
                       "coef": m_wage.table.round(5).to_dict(orient="index")},
        "vif": vifs.round(2).to_dict(),
        f"emp_index_{last}_by_tercile": tr,
        f"focal_index_{last}": cf.to_dict(orient="index"),
    }
    (table_dir / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    return summary
