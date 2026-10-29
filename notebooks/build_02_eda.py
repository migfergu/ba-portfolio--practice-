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

**Research question (A3).** Did U.S. occupations with higher predicted generative-AI task exposure see different employment and wage changes after ChatGPT's late-2022 release, relative to less-exposed occupations in the same industry? **H1:** employment gap < 0 (one-sided). **Wages:** two-sided. Exposure measures *technical potential*, not employer adoption, so every result is a **differential association**, not an effect of GenAI.

**Workflow.** The notebook *imports* the `oews_eda` package (`src/oews_eda/`) and defines no analysis functions of its own:
1. Connect to the A4 database, define the row, trace merges, validate.
2. Univariate analysis.
3. Bivariate analysis.
4. Multivariate analysis.
5. Hypothesis tests with assumption checks, timing analysis and a placebo.
6. Descriptive finance contrast.
7. Business implications and what they mean for A6.

Design answers to the A4 feedback are collected in `docs/A5_RESEARCH_DESIGN.md`.

> **Data status: SYNTHETIC SAMPLE.** The committed database is built from `data/sample/` (seed 751), which mirrors the real file layouts. The generator builds in an exposure-linked employment slowdown and no wage difference, so the results below are a **known-answer test of the code**, not evidence about real occupations. After an authorized `uv run oews-pipeline run --source raw`, re-running this notebook or `uv run oews-eda` regenerates everything on the licensed files. Those files are never committed (`docs/DATA_ACCESS.md`, "Full-data verification")."""),
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
from oews_eda import data, describe, inference, plots, report

pd.set_option("display.float_format", "{:,.4f}".format)
pd.set_option("display.width", 160)
pd.set_option("display.max_colwidth", 90)
FIG = data.REPO_ROOT / "reports" / "figures"
print("oews_eda", oews_eda.__version__, "| database:", data.DEFAULT_DB.relative_to(data.REPO_ROOT))"""),
(MD, """## 1. The analytical panel: definition, sources, crosswalks, attrition, quality

### 1.1 What is one row, and where does each field come from?"""),
(CODE, """display(data.panel_definition())
display(data.CROSSWALKS)"""),
(MD, """One row is a **detailed 2018-SOC occupation × 4-digit NAICS industry × May year**. Employment (a level, not flows) and mean wage (the pay of incumbents) are separate outcomes and are never combined. Exposure is a fixed, occupation-level score of predicted task potential, joined by truncating O*NET-SOC codes to SOC."""),
(MD, """### 1.2 OEWS release structure

Each May estimate pools six semiannual survey panels from three years (BLS technical notes). The panel starts at May 2021, the first MB3 release and the first based entirely on 2018-SOC data, so there is no estimation-method break inside the window. The 2017 → 2022 NAICS switch falls between May 2021 and May 2022."""),
(CODE, """display(data.oews_vintage())"""),
(MD, """### 1.3 Connect, trace attrition, validate

`load_panel()` reads `v_analysis_panel` over a read-only connection. `attrition_table()` counts what survives each filter and merge. `validate_panel()` re-checks the pipeline contract before any statistics are run. OEWS rows are estimates without transaction IDs, so the uniqueness check is about one estimate per natural key, not about duplicate transactions."""),
(CODE, """panel = data.load_panel()
print(f"Source: {panel.attrs['source_mode']} | rows: {len(panel):,} | cells: {panel['cell_id'].nunique()} | "
      f"occupations: {panel['soc_code'].nunique()} | industries: {panel['naics_code'].nunique()}")
attrition = data.attrition_table(panel)
display(attrition)
print("Out-of-grain aggregate rows filtered:", attrition.attrs["out_of_grain_filtered"],
      "| quarantined by validation:", attrition.attrs["quarantined"])
plots.plot_attrition(attrition, FIG / "fig10_merge_attrition.png", panel.attrs["source_mode"]);"""),
(CODE, """qc = data.validate_panel(panel)
print("All checks passed:", qc.passed)
display(pd.Series(qc.checks, name="passed").to_frame())
print(qc.details)
display(qc.coverage)
plots.plot_coverage(qc.coverage, FIG / "fig01_data_coverage.png", panel.attrs["source_mode"]);"""),
(CODE, """# Reproducible run log: input hashes only, no data. A reviewer compares this against their own licensed rebuild.
display(data.input_manifest()[["source_name", "file_name", "version", "sha256", "rows_read", "source_mode"]])"""),
(MD, """**Reading.**
* Of 757 OEWS rows read, 105 are BLS aggregate rows outside the panel grain and 7 are quarantined, leaving 645 facts.
* One occupation (Construction Laborers) has no exposure score, leaving 615 rows; employment suppression leaves 572 model-ready rows.
* That yields 123 cells with both a pre and a post observation, and 87 cells observed in all five years.
* All quality checks pass. The 9-14% of cells per year lost to BLS suppression is why trend views use the balanced cells."""),
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
* Employment is strongly right-skewed (skew ≈ 3.6); its log is near-symmetric (≈ 0.4).
* Wages are bimodal (clerical/service vs. professional occupations); the log removes the remaining skew. Both confirm the A3 choice of log outcomes.
* Exposure is left-skewed in this finance-focused panel. The median occupation (0.74) defines the High/Low split; both focal roles (analysts 0.84, clerks 0.90) are High.
* Relative standard errors exist for every cell, so imprecise cells can be down-weighted in A6 sensitivity checks."""),
(MD, """## 3. Bivariate analysis: exposure vs. change after 2022

`cell_changes()` gives each cell's *mean post-period minus mean pre-period* log outcome (pre = 2021-22, post = 2023+). It also gives a **within-industry** version (`_wi`): the cell's change minus its industry's mean change. The `_wi` version is the A3 comparison group, lower-exposure occupations in the same industry over the same period, so industry-wide shocks cancel."""),
(CODE, """cells = describe.cell_changes(panel)
print("Employment change (approx. %), by exposure group:")
display(describe.group_comparison(cells, "d_log_emp"))
print("Wage change (approx. %), by exposure group:")
display(describe.group_comparison(cells, "d_log_wage"))
print("Exposure vs employment change:", describe.correlation_with_pvalues(cells, "exposure_main", "d_log_emp"))
print("Exposure vs wage change:      ", describe.correlation_with_pvalues(cells, "exposure_main", "d_log_wage"))"""),
(CODE, """occ_emp = describe.occupation_changes(cells, "d_log_emp")
plots.plot_exposure_vs_change(cells, occ_emp, "d_log_emp", FIG / "fig04_exposure_vs_emp_change.png",
                              panel.attrs["source_mode"]);"""),
(CODE, """balanced = data.balanced_cells(panel, "log_emp")
trend = describe.trend_index(balanced, "exposure_tercile", "log_emp")
display(trend.pivot(index="year", columns="group", values="index"))
plots.plot_trend_index(trend, "Employment", FIG / "fig05_emp_trend_by_exposure.png", panel.attrs["source_mode"]);"""),
(MD, """**Reading.**
* Employment in high-exposure cells grew about +2.7% from the pre to the post period, against about +5.6% in low-exposure cells. The scatter slopes down: roughly 1 point less growth per +0.1 exposure.
* The balanced-panel index shows the terciles moving roughly together through 2022 and separating afterwards.
* Wage changes are unrelated to exposure (r ≈ 0)."""),
(MD, """## 4. Multivariate analysis

(a) How do exposure, preparation, pay and size relate to each other? (b) Does the exposure-employment association survive controls for preparation, pre-period pay and industry? Standard errors are clustered by occupation (CR1, G − 1 df), because exposure varies only across occupations."""),
(CODE, """corr_cols = ["exposure_main", "job_zone_mean", "pre_log_wage", "pre_log_emp", "d_log_emp", "d_log_wage"]
corr = describe.correlation_table(cells, corr_cols)
display(corr)
plots.plot_correlation_heatmap(corr, report.LABELS, FIG / "fig06_correlation_heatmap.png", panel.attrs["source_mode"]);"""),
(CODE, """X = ["exposure_z", "job_zone_mean", "pre_log_wage"]
print("Multicollinearity check (VIF; < 5 acceptable):")
display(inference.vif(cells, X).to_frame())
m_emp = inference.ols_cluster(cells, "d_log_emp", X, fixed_effects=["naics_code"])
m_wage = inference.ols_cluster(cells, "d_log_wage", X, fixed_effects=["naics_code"])
for m in (m_emp, m_wage):
    print(f"\\n{m.formula}   n = {m.n_obs}, occupation clusters = {m.n_clusters}, R² = {m.r2:.3f}")
    display(m.table)
plots.plot_coefficients(m_emp.table, report.LABELS, path=FIG / "fig07_model_coefficients.png",
                        source_mode=panel.attrs["source_mode"]);"""),
(MD, """**Reading.**
* Job Zone and pre-period wage are strongly correlated with each other (ρ ≈ 0.8, VIF ≈ 4), but neither is strongly correlated with exposure (|ρ| ≤ 0.17). Exposure is therefore not a proxy for skill or pay.
* With industry fixed effects and those controls, one standard deviation more exposure is **associated** with about 2.6 points less employment growth. The occupation-clustered 95% CI is −3.4 to −1.8.
* In the wage model exposure shows no association (CI spans 0); Job Zone is the only wage predictor."""),
(MD, """## 5. Hypothesis tests

A gap is treated as **practically meaningful** only if it is at least 1 percentage point of growth over the post period (`report.PRACTICAL_THRESHOLD`). Each test's occupation-cluster CI is classified against that band, so "not significant" is never read as "no effect".

### 5.1 Employment: A3 H1 (primary, within industry)

* **H₀:** μ_High − μ_Low ≥ 0. Relative to their industry, high-exposure cells' employment grew at least as fast as low-exposure cells' after 2022.
* **H₁:** μ_High − μ_Low < 0. It grew more slowly.
* **α = 0.05.** Unit: occupation × industry cell; outcome: within-industry change in log employment (`d_log_emp_wi`).

**Assumptions checked.**
* Normality within each group: Shapiro-Wilk plus Q-Q plots.
* Equal variances: Levene, median-centred. The result picks Student's t or Welch's t.
* Independence is the weak point: cells of one occupation share one exposure score. The test is therefore paired with an occupation-cluster bootstrap CI and an occupation-level permutation test (n = occupations).
* Mann-Whitney U is reported as a distribution-free check."""),
(CODE, """t_emp = inference.exposure_group_test(cells, "d_log_emp_wi", alternative="less",
                                     practical_threshold=report.PRACTICAL_THRESHOLD)
display(pd.Series(t_emp.assumptions, name="assumption checks").to_frame())
print(f"{t_emp.test_used}: t = {t_emp.statistic:.3f}, p = {t_emp.p_value:.2e}  ->  {t_emp.decision}")
print(f"Hedges' g = {t_emp.hedges_g:.2f};  Mann-Whitney p = {t_emp.mann_whitney_p:.2e}")
print(f"Occupation-cluster 95% CI for the gap (pp): [{t_emp.cluster_ci_low*100:.2f}, {t_emp.cluster_ci_high*100:.2f}]"
      f"  ->  {t_emp.practical_verdict}")
print("Occupation-level permutation test:", inference.occupation_permutation_test(occ_emp, alternative="less"))
print()
print(t_emp.interpretation)
plots.plot_group_test(cells, "d_log_emp_wi", t_emp, FIG / "fig08_hypothesis_test_emp.png", panel.attrs["source_mode"]);"""),
(MD, """**Interpretation.**
* Both groups pass Shapiro-Wilk (p > 0.25) and the Q-Q plots are straight, so normality holds. Levene rejects equal variances narrowly (p ≈ 0.048), so the function selects **Welch's t**.
* We **reject H₀**. Relative to their industries, high-exposure cells' employment grew about 2.7 points less than low-exposure cells' (g ≈ −0.8, medium-to-large).
* The result does not rest on treating cells as independent: the occupation-cluster CI (−4.4 to −1.3 pp) excludes zero, and the 19-occupation permutation test agrees.
* The whole CI lies beyond the 1-point band, so the gap is **practically meaningful**, not just detectable.
* It remains a differential association between predicted exposure and employment, not a measured impact of GenAI adoption."""),
(MD, """### 5.2 Wages (two-sided, within industry)

* **H₀:** μ_High − μ_Low = 0 for the within-industry change in log mean wage. **H₁:** ≠ 0."""),
(CODE, """t_wage = inference.exposure_group_test(cells, "d_log_wage_wi", alternative="two-sided",
                                      practical_threshold=report.PRACTICAL_THRESHOLD)
print(f"{t_wage.test_used}: p = {t_wage.p_value:.3f}, g = {t_wage.hedges_g:.2f}, cluster CI (pp) "
      f"[{t_wage.cluster_ci_low*100:.2f}, {t_wage.cluster_ci_high*100:.2f}] -> {t_wage.decision}; {t_wage.practical_verdict}")
print(t_wage.interpretation)"""),
(MD, """**Interpretation.**
* We **fail to reject H₀**: no wage difference is detected (g ≈ 0).
* The CI (about −1.2 to +1.0 pp) still reaches past the 1-point band on both sides, so the verdict is **inconclusive**, not "no wage effect": a small but meaningful pay gap cannot be ruled out.
* Mean wage is the pay of incumbents, so a cell that loses jobs can show a wage change purely from who remains. Employment and wages stay separate outcomes."""),
(MD, """### 5.3 Timing: event-time gaps, panel pooling, delayed post, NAICS change

Each May estimate pools six survey panels from three years. Only 1 of 6 panels in May 2023 post-dates ChatGPT, 3 of 6 in May 2024 and 5 of 6 in May 2025. Any real change therefore appears gradually in OEWS even if it happened all at once."""),
(CODE, """gaps = inference.event_time_gaps(describe.cell_year_changes(panel, "log_emp"))
display(gaps.merge(data.oews_vintage()[["post_chatgpt_panels"]], left_on="year", right_index=True))
plots.plot_event_time_gaps(gaps, data.oews_vintage(), FIG / "fig11_event_time_gaps_emp.png", panel.attrs["source_mode"])

kw = {"alternative": "less", "practical_threshold": report.PRACTICAL_THRESHOLD}
t_del = inference.exposure_group_test(describe.cell_changes(panel, post_col="post_delayed"), "d_log_emp_wi", **kw)
t_no21 = inference.exposure_group_test(describe.cell_changes(panel[panel["year"] != 2021]), "d_log_emp_wi", **kw)
for name, t in (("Delayed post (2024+)", t_del), ("Excluding May 2021 (2017 NAICS)", t_no21)):
    print(f"{name:34s} gap {t.diff_pct_points:+.2f}%, p = {t.p_value:.1e}, cluster CI (pp) "
          f"[{t.cluster_ci_low*100:.2f}, {t.cluster_ci_high*100:.2f}] -> {t.decision}; {t.practical_verdict}")"""),
(MD, """**Interpretation.**
* On the sample the gap is about 0 in 2023, −2.4 pp in 2024 and −5.3 pp in 2025, and the delayed-post test gives a larger gap (≈ −3.9 pp). **These values describe the synthetic generator, not OEWS pooling:** the generator plants an effect proportional to (year − 2022) and does not simulate pooled survey panels, so the build-up here is the planted ramp plus noise. The near-zero 2023 value is an unusual seed draw (about 1 in 200), not a code defect: on noise-free data the code recovers the planted 2023 gap (`docs/A6_EVALUATION_REPORT.md` §1). With real data, compare the timing against the post-ChatGPT panel share printed under each year: a gap that tracks that share is what pooling alone would produce and is not by itself evidence of gradual adoption. A6 reports event-time coefficients and a panel-share timing specification.
* Dropping May 2021 (the only 2017-NAICS release) keeps a significant gap (≈ −2.5 pp), but its CI now reaches inside the 1-point band (*detectable, size uncertain*). The NAICS change is a sensitivity to carry into A6."""),
(MD, """### 5.4 Placebo: 2021 → 2022 (both pre-ChatGPT)

* **H₀:** no exposure gap in the within-industry 2021 → 2022 employment change. **H₁:** a gap exists. Two-sided.
* A real gap here would mean exposure groups were already diverging before ChatGPT, which would undercut the comparison."""),
(CODE, """pre = describe.pre_period_change(panel, "log_emp").merge(cells[["cell_id"]], on="cell_id")
t_pl = inference.exposure_group_test(pre, "d_pre_log_emp", alternative="two-sided",
                                    practical_threshold=report.PRACTICAL_THRESHOLD)
print(f"Placebo: gap {t_pl.diff_pct_points:+.2f}%, p = {t_pl.p_value:.2f}, cluster CI (pp) "
      f"[{t_pl.cluster_ci_low*100:.2f}, {t_pl.cluster_ci_high*100:.2f}] -> {t_pl.decision}; {t_pl.practical_verdict}")"""),
(MD, """**Interpretation.**
* No pre-period gap is detected (−0.5 pp, p ≈ 0.50). Parallel pre-trends are therefore *not contradicted*.
* With two pre years the CI (−2.1 to +0.9 pp) is wide, so they are *not established* either.
* A causal reading would further need:
  * no concurrent occupation-specific shock correlated with exposure;
  * actual adoption that rises with predicted exposure;
  * no spillovers onto low-exposure occupations;
  * stable cell composition.

  None of these can be checked with these fields (`docs/A5_RESEARCH_DESIGN.md` §5)."""),
(MD, """## 6. Finance contrast (descriptive only, per A3 feedback)

Financial & investment analysts (13-2051) vs. bookkeeping, accounting & auditing clerks (43-3031), each on its industry cells observed in every year, indexed to 2022 = 100."""),
(CODE, """contrast = describe.focal_contrast(panel)
display(contrast)
plots.plot_focal_contrast(contrast, FIG / "fig09_analyst_vs_clerk.png", panel.attrs["source_mode"]);"""),
(MD, """**Reading.**
* Both roles grow after 2022 in the sample, and both sit at the high-exposure end of the Section 3 slope.
* With 2-3 industries per role this is context, not a test. Whether GenAI complements analysts' tasks while substituting for clerks' cannot be answered with these fields. The A6 analyst-by-post interaction will quantify the contrast; here it stays descriptive."""),
(MD, """## 7. Findings, business implications, and implications for modeling

| # | Finding (sample run; known-answer test) | Business implication (if the real data agree) | Implication for A6 |
|---|---|---|---|
| 1 | Within industry, employment in high-exposure cells grew ~2.7 pp less; practically meaningful (CI beyond ±1 pp); survives controls, clustering and nonparametric checks | Plan a slower-headcount-growth scenario for exposed roles alongside the baseline | Expect negative β on employment; keep occupation-clustered SEs and industry-by-year FE |
| 2 | On the sample the gap grows with event time (≈0 → −2.4 → −5.3 pp); this is the generator's planted ramp, not a pooling result | With real data, check the timing against the post-ChatGPT panel share before reading it as adoption speed; revisit with each release | Event-time coefficients and a panel-share timing variable, not a single post dummy |
| 3 | No detectable wage gap, but ±1 pp not ruled out | No GenAI pay discount is justified; keep monitoring | Wage stays two-sided; report CIs against the 1-pp band |
| 4 | Placebo 2021 → 2022 shows no gap (wide CI) | The high-vs-low comparison is credible but not proven | Formal pre-period coefficients; note only two pre years |
| 5 | Exposure is nearly uncorrelated with preparation and pay | Exposure is a separate planning dimension from skill or pay band | Job Zone as moderator, not confounder; VIFs < 5 |
| 6 | 9-14% of cells per year suppressed; excluding May 2021 weakens the size estimate | Small occupation-industry groups are under-represented | Balanced vs unbalanced estimates; PRSE weighting; NAICS sensitivity |

**Not supported by these fields:** GenAI adoption or use; causal displacement or augmentation; hires vs separations (employment is a level); individual worker outcomes; hours or total compensation; firm or regional patterns. The non-technical version is `docs/A5_EXECUTIVE_SUMMARY.md`."""),
(MD, """## 8. Regenerate every output and the run log in one call

`report.run_all()` re-runs everything above and writes figures (`reports/figures/`), tables, the JSON summary and the checksum run log (`reports/eda/`). The same entry point is `uv run oews-eda`, and `uv run oews-eda --verify-against reports/eda/eda_run_log.json` checks a rebuilt database's inputs against the log."""),
(CODE, """summary = report.run_all()
print("Figures:", sorted(p.name for p in FIG.glob("fig*.png")))
display(pd.read_csv(data.REPO_ROOT / "reports" / "eda" / "hypothesis_tests.csv", index_col=0)
        [["test", "p", "gap_pct", "cluster_ci_low_pct", "cluster_ci_high_pct", "decision", "practical_verdict"]])
print("Data:", summary["source_mode"])"""),
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
