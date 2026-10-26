"""Builds notebooks/02_eda.ipynb (kept as a script so the notebook's structure is reviewable in diffs).

Run:  uv run python notebooks/build_02_eda.py   then open and "Run All" in Jupyter.
"""
from __future__ import annotations

import json
from pathlib import Path

MD, CODE = "markdown", "code"
CELLS: list[tuple[str, str]] = [
(MD, """# Assignment 5 - Exploratory Data Analysis
## Generative AI Exposure and Financial Analyst Employment and Wages

**BUS 751 · Miguel L. Ferguson II · Pathway 2 (research-oriented)**

**Research question (A3).** Did U.S. occupations with higher generative-AI task exposure see different employment and wage changes after ChatGPT's late-2022 release? A3 hypotheses: **H1** employment effect β < 0; wage effect two-sided. Results are associations, not proof of displacement or augmentation.

**What this notebook does.** It *imports* the reusable `oews_eda` package (`src/oews_eda/`) and walks through the workflow: connect to the A4 database and validate it → univariate → bivariate → multivariate → hypothesis tests with assumption checks → descriptive finance contrast → business implications and what they mean for A6 modeling. No analysis logic is defined in the notebook.

> **Data note.** The committed database is built from the A4 **synthetic sample** (`data/sample/`, seed 751), which mirrors the real file layouts. Every number below demonstrates the method and must not be interpreted as evidence about real occupations. After `uv run oews-pipeline run --source raw`, re-running this notebook (or `uv run oews-eda`) regenerates every table, figure and test on the real OEWS data with no code change. Each figure footnote states which data it was drawn from."""),
(CODE, """# Setup: import the analysis package (installed by `uv sync`; the path fallback covers a bare Jupyter kernel)
import sys
from pathlib import Path

try:
    import oews_eda
except ModuleNotFoundError:
    sys.path.insert(0, str(Path.cwd().resolve().parent / "src"))
    import oews_eda

import pandas as pd
from IPython.display import display
from oews_eda import data, describe, inference, plots

pd.set_option("display.float_format", "{:,.4f}".format)
pd.set_option("display.width", 140)
FIG = data.REPO_ROOT / "reports" / "figures"
print("oews_eda", oews_eda.__version__, "| database:", data.DEFAULT_DB.relative_to(data.REPO_ROOT))"""),
(MD, """## 1. Connect to the A4 database and validate data quality

`data.load_panel()` reads the `v_analysis_panel` view (read-only connection) and adds the derived variables used throughout: log outcomes, event time (2022 = 0), occupation-level exposure groups. `data.validate_panel()` re-checks the contract the pipeline promised before any statistics are run."""),
(CODE, """panel = data.load_panel()
print(f"Source: {panel.attrs['source_mode']} | rows: {len(panel):,} | cells: {panel['cell_id'].nunique()} | "
      f"occupations: {panel['soc_code'].nunique()} | industries: {panel['naics_code'].nunique()}")
qc = data.validate_panel(panel)
print("All checks passed:", qc.passed)
display(pd.Series(qc.checks, name="passed").to_frame())
print(qc.details)
display(qc.coverage)"""),
(CODE, """plots.plot_coverage(qc.coverage, FIG / "fig01_data_coverage.png", panel.attrs["source_mode"]);"""),
(MD, """**Reading.** The key is unique, years are complete, BLS suppression flags agree with NULL values, and exposures are in range. One panel occupation (Construction Laborers, 47-2061) has no exposure score; it is kept in the panel but drops out of exposure analyses (~5% of rows). Between 86% and 91% of cells are model-ready each year; the rest are lost mainly to BLS employment suppression (`**`), so trend views below use a **balanced** set of cells to keep composition fixed."""),
(MD, """## 2. Univariate analysis"""),
(CODE, """display(describe.univariate_summary(panel, ["tot_emp", "log_emp", "a_mean", "log_wage",
                                             "exposure_main", "job_zone_mean", "emp_prse", "mean_prse"]))
occ = describe.occupation_table(panel)
display(occ[["occ_title", "exposure_main", "job_zone_mean", "exposure_group", "exposure_tercile",
             "pre_emp_total", "pre_mean_wage"]])"""),
(CODE, """plots.plot_exposure_distribution(occ, panel.attrs["exposure_median"], FIG / "fig02_exposure_distribution.png",
                                 panel.attrs["source_mode"]);"""),
(CODE, """plots.plot_outcome_distributions(panel, FIG / "fig03_outcome_distributions.png", panel.attrs["source_mode"]);"""),
(MD, """**Reading.**
* Employment is strongly right-skewed (skew ≈ 3.6, a few very large cells); its log is close to symmetric (≈ 0.4). Wages are bimodal (low-wage service/clerical vs. professional occupations) and the log removes the remaining skew. This confirms the A3 choice to model **log** employment and **log** mean wage.
* Exposure is left-skewed: most occupations in this finance-focused panel sit between 0.55 and 0.95; manual occupations anchor the low end. The median occupation exposure (0.74) defines the High/Low split; both focal occupations (analysts 0.84, clerks 0.90) are High.
* Relative standard errors (EMP_PRSE, MEAN_PRSE) are available for every cell, so imprecise cells can be down-weighted or dropped in A6 sensitivity checks."""),
(MD, """## 3. Bivariate analysis: exposure vs. change after ChatGPT

`describe.cell_changes()` collapses each occupation × industry cell to *mean post-period log outcome − mean pre-period log outcome* (pre = 2021-22, post = 2023+). This is the cell-level analogue of the A3 difference-in-differences contrast and tolerates a suppressed year."""),
(CODE, """cells = describe.cell_changes(panel)
print("Employment change (approx. %), by exposure group:")
display(describe.group_comparison(cells, "d_log_emp"))
print("Wage change (approx. %), by exposure group:")
display(describe.group_comparison(cells, "d_log_wage"))
print("Cell-level correlation, exposure vs employment change:", describe.correlation_with_pvalues(cells, "exposure_main", "d_log_emp"))
print("Cell-level correlation, exposure vs wage change:      ", describe.correlation_with_pvalues(cells, "exposure_main", "d_log_wage"))"""),
(CODE, """occ_emp = describe.occupation_changes(cells, "d_log_emp")
plots.plot_exposure_vs_change(cells, occ_emp, "d_log_emp", FIG / "fig04_exposure_vs_emp_change.png",
                              panel.attrs["source_mode"]);"""),
(CODE, """balanced = data.balanced_cells(panel, "log_emp")
trend = describe.trend_index(balanced, "exposure_tercile", "log_emp")
display(trend.pivot(index="year", columns="group", values="index"))
plots.plot_trend_index(trend, "Employment", FIG / "fig05_emp_trend_by_exposure.png", panel.attrs["source_mode"]);"""),
(MD, """**Reading.** Employment in high-exposure cells grew roughly half as fast as in low-exposure cells after 2022 (≈ +2.7% vs ≈ +5.6%), and the scatter shows a clear downward slope. The balanced-panel trend matters for the A6 design: the three exposure terciles move roughly together through 2022 (pre-trends look approximately parallel) and separate only afterwards. Wage changes show **no** relationship with exposure (r ≈ 0)."""),
(MD, """## 4. Multivariate analysis

Two questions: (a) how do exposure, preparation (Job Zone), pay and size relate to each other? (b) Does the exposure-employment association survive controls for preparation, pre-period pay and industry? Standard errors are clustered by occupation (CR1, G − 1 df), because exposure varies only across occupations."""),
(CODE, """corr_cols = ["exposure_main", "job_zone_mean", "pre_log_wage", "pre_log_emp", "d_log_emp", "d_log_wage"]
corr = describe.correlation_table(cells, corr_cols)
display(corr)
from oews_eda.report import LABELS
plots.plot_correlation_heatmap(corr, LABELS, FIG / "fig06_correlation_heatmap.png", panel.attrs["source_mode"]);"""),
(CODE, """X = ["exposure_z", "job_zone_mean", "pre_log_wage"]
print("Multicollinearity check (VIF; < 5 acceptable):")
display(inference.vif(cells, X).to_frame())
m_emp = inference.ols_cluster(cells, "d_log_emp", X, fixed_effects=["naics_code"])
m_wage = inference.ols_cluster(cells, "d_log_wage", X, fixed_effects=["naics_code"])
for m in (m_emp, m_wage):
    print(f"\\n{m.formula}   n = {m.n_obs}, occupation clusters = {m.n_clusters}, R² = {m.r2:.3f}")
    display(m.table)"""),
(CODE, """plots.plot_coefficients(m_emp.table, LABELS, path=FIG / "fig07_model_coefficients.png",
                        source_mode=panel.attrs["source_mode"]);"""),
(MD, """**Reading.** Job Zone and pre-period wage are highly correlated with each other (ρ ≈ 0.8, VIF ≈ 4), but neither is strongly correlated with exposure (|ρ| ≤ 0.17), so exposure is not simply proxying for skill or pay. With industry fixed effects and those controls, a one-standard-deviation increase in exposure is associated with about **2.6 percentage points less employment growth** (95% CI clustered by occupation excludes zero). The wage model shows no exposure association; preparation (Job Zone) is the only wage predictor. Industry fixed effects absorb sector-wide shocks, which previews the industry-by-year fixed effects in the A3 specification."""),
(MD, """## 5. Hypothesis tests

### 5.1 Employment (A3 H1, one-sided)

* **H₀:** μ_High − μ_Low ≥ 0 — high-exposure cells' employment grew at least as fast as low-exposure cells' after 2022.
* **H₁:** μ_High − μ_Low < 0 — high-exposure cells' employment grew more slowly.
* **α = 0.05.** Unit: occupation × industry cell; outcome: change in log employment (post − pre).

**Assumptions checked:** normality within each group (Shapiro-Wilk + Q-Q plots), equal variances (Levene, median-centred), independence. Independence is the weak point: cells of the same occupation share one exposure score, so the test is paired with (i) an occupation-cluster bootstrap CI and (ii) an occupation-level permutation test (n = occupations). Mann-Whitney U is reported as a distribution-free check."""),
(CODE, """t_emp = inference.exposure_group_test(cells, "d_log_emp", alternative="less")
display(pd.Series(t_emp.assumptions, name="assumption checks").to_frame())
print(f"{t_emp.test_used}: t = {t_emp.statistic:.3f}, p = {t_emp.p_value:.2e}  ->  {t_emp.decision}")
print(f"Hedges' g = {t_emp.hedges_g:.2f};  Mann-Whitney p = {t_emp.mann_whitney_p:.2e}")
print(f"Occupation-cluster bootstrap 95% CI for the gap (log points): [{t_emp.cluster_ci_low:.4f}, {t_emp.cluster_ci_high:.4f}]")
print("Occupation-level permutation test:", inference.occupation_permutation_test(occ_emp, alternative="less"))
print()
print(t_emp.interpretation)"""),
(CODE, """plots.plot_group_test(cells, "d_log_emp", t_emp, FIG / "fig08_hypothesis_test_emp.png", panel.attrs["source_mode"]);"""),
(MD, """**Interpretation.** Both groups pass the normality check (Shapiro-Wilk p > 0.05, straight Q-Q plots) and Levene does not reject equal variances (p ≈ 0.06, borderline), so Student's t applies; Welch's t gives the same conclusion. We **reject H₀**: high-exposure cells' employment grew about 2.8% less than low-exposure cells', a medium-to-large effect (g ≈ −0.8). The conclusion does not depend on treating cells as independent: the occupation-cluster bootstrap CI excludes zero and the occupation-level permutation test (19 occupations) is also significant. Mann-Whitney agrees, so the result is not driven by outliers."""),
(MD, """### 5.2 Wages (two-sided) and the delayed-post robustness check

* **H₀:** μ_High − μ_Low = 0 for the change in log mean wage; **H₁:** ≠ 0.
* Robustness (A3): repeat the employment test with the delayed post period (2024+), in case adoption lagged ChatGPT's release."""),
(CODE, """t_wage = inference.exposure_group_test(cells, "d_log_wage", alternative="two-sided")
print(f"WAGES  {t_wage.test_used}: p = {t_wage.p_value:.3f}, g = {t_wage.hedges_g:.2f}, cluster CI "
      f"[{t_wage.cluster_ci_low:.4f}, {t_wage.cluster_ci_high:.4f}] -> {t_wage.decision}")
print(t_wage.interpretation)
cells_delayed = describe.cell_changes(panel, post_col="post_delayed")
t_del = inference.exposure_group_test(cells_delayed, "d_log_emp", alternative="less")
print(f"\\nEMPLOYMENT, delayed post (2024+): p = {t_del.p_value:.2e}, g = {t_del.hedges_g:.2f}, "
      f"gap = {t_del.diff_pct_points:.1f}% -> {t_del.decision}")"""),
(MD, """**Interpretation.** We **fail to reject H₀** for wages: there is no detectable wage difference between high- and low-exposure cells (g ≈ 0, CI spans zero). With the delayed post period the employment gap is *larger* (≈ −4% vs ≈ −2.8%), which is what a gradually building adoption effect would look like and supports the A3 plan to estimate event-time coefficients rather than a single post dummy."""),
(MD, """## 6. Finance contrast (descriptive only, per A3 feedback)

Financial & investment analysts (13-2051) vs. bookkeeping, accounting & auditing clerks (43-3031), each on its industry cells observed in every year, indexed to 2022 = 100. With only 2-3 industries per role this is context, not a test."""),
(CODE, """contrast = describe.focal_contrast(panel)
display(contrast)
plots.plot_focal_contrast(contrast, FIG / "fig09_analyst_vs_clerk.png", panel.attrs["source_mode"]);"""),
(MD, """**Reading.** In the sample both roles grow after 2022, and the cross-occupation slope in Section 3 places both near the high-exposure end of the fitted line. Whether GenAI complements analysts' tasks while substituting for clerks' is a hypothesis this EDA cannot test with 2-3 industries per role; the A6 analyst-by-post interaction is where the contrast will be quantified, so here it stays descriptive."""),
(MD, """## 7. Findings, business implications, and what they mean for modeling

| # | Finding (sample run) | Business implication | Implication for A6 modeling |
|---|---|---|---|
| 1 | Employment grew ~2.8% less in high-exposure cells after 2022; holds with controls, industry FE, occupation clustering, and nonparametric tests | Workforce plans for GenAI-exposed roles (analysts, accountants, data entry, developers) should assume slower headcount growth, not flat-line growth | Main TWFE β on employment is expected negative; keep occupation-clustered SEs |
| 2 | The gap widens with the delayed post (2024+) | Effects build over time; one year of post data understates them | Estimate event-time coefficients (2022 reference), not only a single post dummy |
| 3 | No wage difference by exposure | Exposure is changing *how many* people are hired before it changes *what they are paid*; pay benchmarks do not need a GenAI discount yet | Wage outcome stays two-sided; expect a null or small β |
| 4 | Pre-period trends by exposure tercile are parallel | Comparisons between high- and low-exposure roles are credible | Supports the DiD identifying assumption; test formally with pre-period event-time coefficients |
| 5 | Exposure is nearly uncorrelated with preparation and pay | GenAI exposure is a distinct risk dimension, not a proxy for "high-skill" or "high-pay" | Job Zone can be a moderator, not a confounder; VIFs < 5 |
| 6 | 9-14% of cells per year are lost to suppression | Small occupation-industry cells are under-represented | Report balanced vs unbalanced estimates; weight or drop high-PRSE cells in sensitivity |

The non-technical version is in `docs/A5_EXECUTIVE_SUMMARY.md`."""),
(MD, """## 8. Regenerate every output in one call

`report.run_all()` re-runs everything above and writes the figures (`reports/figures/`), tables and a JSON summary (`reports/eda/`). The same entry point is available as `uv run oews-eda`."""),
(CODE, """from oews_eda import report
summary = report.run_all()
print("Figures:", sorted(p.name for p in FIG.glob("fig*.png")))
print("Headline:", summary["test_emp"]["decision"], "| employment gap (approx. %):",
      round(summary["test_emp"]["diff_pct_points"], 2), "| data:", summary["source_mode"])"""),
]


def build(path: Path) -> None:
    """Write the notebook JSON (no outputs) to ``path``."""
    nb = {"cells": [], "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                    "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    for i, (kind, src) in enumerate(CELLS):
        cell = {"cell_type": kind, "id": f"cell-{i:02d}", "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == CODE:
            cell.update(execution_count=None, outputs=[])
        nb["cells"].append(cell)
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    build(Path(__file__).with_name("02_eda.ipynb"))
