# EDA Methodology and Code Documentation (Assignment 5)

## Run it

```powershell
uv sync                         # installs matplotlib, seaborn, scipy (added for A5)
uv run oews-pipeline run        # A4: build data/processed/oews_genai.db (sample) - or --source raw
uv run oews-eda                 # A5: all figures, tables, tests -> reports/figures, reports/eda
uv run jupyter lab notebooks/02_eda.ipynb   # walkthrough; "Run All" reproduces the committed outputs
uv run pytest -q                # 22 tests: 11 A4 + 11 A5
uv run oews-eda --verify-against reports/eda/eda_run_log.json   # input checksum check
```

`uv run python notebooks/build_02_eda.py` regenerates the notebook skeleton from a reviewable script.

## Integration with the A4 pipeline

The EDA reads only the `v_analysis_panel` view through a **read-only** SQLite connection (`oews_eda.data.connect`), so it cannot alter the database and never re-implements ETL. The latest successful `etl_run.source_mode` (`sample` or `raw`) is attached to the panel and printed in every figure footnote, so a sample figure can never be mistaken for a real-data result. Each run also writes `reports/eda/eda_run_log.json` (input SHA-256s, versions, code commit), and `--verify-against` checks a rebuilt database against it; see `docs/DATA_ACCESS.md`. Row definition, source of each field, crosswalks and merge attrition are in `docs/A5_RESEARCH_DESIGN.md` §1-3. Before any statistics, `validate_panel` re-checks the pipeline contract: unique key, complete years, suppression flags consistent with NULLs, exposure in [0, 1], positive values, and exposure coverage ≥ 80%. `run_all` stops with a named error if any check fails.

## Package layout (`src/oews_eda/`)

| Module | Key functions | Purpose |
|---|---|---|
| `data.py` | `load_panel`, `validate_panel`, `add_exposure_groups`, `balanced_cells`, `panel_definition`, `oews_vintage`, `attrition_table`, `input_manifest`, `compare_manifest` | Connection, derived variables, quality gate, row definition, BLS vintages, merge attrition, checksum verification |
| `describe.py` | `univariate_summary`, `occupation_table`, `cell_changes`, `group_comparison`, `correlation_table`, `occupation_changes`, `cell_year_changes`, `pre_period_change`, `trend_index`, `focal_contrast` | Univariate, bivariate and multivariate description |
| `inference.py` | `check_assumptions`, `hedges_g`, `cluster_bootstrap_diff`, `exposure_group_test`, `occupation_permutation_test`, `practical_significance`, `event_time_gaps`, `ols_cluster`, `vif` | Hypothesis tests, assumption checks, effect sizes, practical-significance verdicts, event-time gaps, cluster-robust OLS |
| `plots.py` | `plot_coverage` … `plot_event_time_gaps` (11 figures) | Static, colorblind-safe stakeholder figures |
| `report.py` | `run_all`, `run_log` | Regenerates every output; writes `eda_summary.json`, `hypothesis_tests.csv`, `eda_run_log.json` |
| `__main__.py` | `main` | `uv run oews-eda` / `python -m oews_eda` |

Every public function has a docstring stating inputs, outputs and the analytical choice it encodes. The notebook imports these functions and defines none of its own.

## Analytical choices

**Unit and outcomes.** Occupation × 4-digit industry × May year, as in A3. Outcomes are log employment and log mean annual wage; the univariate step confirms logs are needed (employment skew 3.6 → 0.4 in logs).

**Pre/post change per cell.** `cell_changes` computes mean post-period log outcome minus mean pre-period log outcome (pre = 2021-22; post = 2023+, or 2024+ for the delayed-post check). Averaging within period uses all available years and tolerates one suppressed year. This is the cell-level analogue of the A3 difference-in-differences contrast; the full two-way fixed-effects model is A6.

**Comparison group (within industry).** `cell_changes` also returns `d_log_emp_wi` / `d_log_wage_wi`: the cell's change minus its industry's mean change. The primary tests use these, so the contrast is high- vs low-exposure occupations *in the same industry over the same period*, the long-difference analogue of the A3 industry-by-year fixed effects. The raw-change test is reported alongside.

**Event time and OEWS pooling.** `cell_year_changes` measures each cell against its own 2022 value (2022 = 0) and subtracts the industry-by-year mean; `event_time_gaps` gives the High − Low gap per year with occupation-cluster CIs (Figure 11). Each May estimate pools six semiannual panels from three years, so the share of post-ChatGPT panels is 0, 0, 1/6, 3/6, 5/6 for 2021-2025 (`data.OEWS_VINTAGE`). That share is printed under every year, because pooling alone makes a real change appear gradually. `pre_period_change` gives the 2021 → 2022 placebo outcome.

**Exposure groups.** Median split and terciles are formed over **occupations**, not cells, so an occupation present in many industries does not shift the cut-off. Ties at the median are classed Low (strict `>` rule).

**Dependence.** Exposure varies only across occupations, so cells of one occupation are not independent. Every cell-level result is paired with an occupation-level check: an occupation-cluster bootstrap CI (2,000 resamples of whole occupations), a permutation test of the Spearman correlation with n = occupations (10,000 permutations), and CR1 cluster-robust standard errors by occupation with G − 1 degrees of freedom in the regression. CR1 uses the same small-sample correction, G/(G−1) × (N−1)/(N−K), as Stata and `statsmodels` `cov_type="cluster"`; it is implemented in NumPy/SciPy so no extra dependency is needed, and a unit test checks the point estimates against `scipy.stats.linregress`.

**Hypothesis test (rubric: stated, assumptions checked, interpreted).**
* H₀: μ_High − μ_Low ≥ 0 vs H₁: μ_High − μ_Low < 0 for the employment change (A3 H1); two-sided for wages.
* `check_assumptions` runs Shapiro-Wilk per group (plus Q-Q plots in Figure 8) and Levene (median-centred). The test is chosen from those results: Student's t (equal variances), Welch's t (unequal), or Mann-Whitney U (non-normal small samples). Mann-Whitney is always reported as a distribution-free check.
* Effect size: Hedges' g. **Practical significance:** the occupation-cluster CI is classified against a pre-set minimum meaningful gap of 1 percentage point (`report.PRACTICAL_THRESHOLD`) as practically meaningful, practically negligible, detectable but of uncertain size, or inconclusive (`inference.practical_significance`). This keeps "not significant" from being read as "no effect".
* Robustness set (`reports/eda/hypothesis_tests.csv`): raw change, delayed post (2024+), excluding May 2021 (the only 2017-NAICS release), and the 2021 → 2022 placebo.
* Interpretation is written by the function itself (`GroupTestResult.interpretation`) and states the business-scale gap (approximate %), significance, whether the occupation-cluster CI agrees, the practical verdict, and the reminder that the result is an association.

**Multivariate model.** `ols_cluster(d_log_emp ~ exposure_z + job_zone_mean + pre_log_wage | industry FE)`. VIFs are all below 5 (Job Zone and pre-period wage are correlated, ρ ≈ 0.8, but neither strongly with exposure).

**Trends.** `trend_index` is a geometric-mean index (2022 = 100) on a balanced set of cells observed in every year, so suppression churn does not create false trends.

**Finance contrast.** Descriptive only, per the A3 instructor note: analysts (13-2051) vs clerks (43-3031) on each role's cells observed in all years, indexed to 2022.

## Figures (`reports/figures/`, 300 dpi)

| File | Question it answers | Chart choice |
|---|---|---|
| fig01_data_coverage | How much of the panel is usable each year? | Stacked bars with hatching |
| fig02_exposure_distribution | How is exposure distributed; where are the focal roles? | Histogram + rug + markers |
| fig03_outcome_distributions | Do outcomes need logs? | Raw vs log histograms with skew |
| fig04_exposure_vs_emp_change | Does exposure relate to employment change? | Scatter, occupation means, fit line |
| fig05_emp_trend_by_exposure | When do groups diverge; are pre-trends parallel? | Indexed lines, distinct markers and dashes |
| fig06_correlation_heatmap | How do the variables relate jointly? | Annotated lower-triangle heatmap |
| fig07_model_coefficients | Does the association survive controls? | Coefficient plot with clustered 95% CIs |
| fig08_hypothesis_test_emp | Test result and its assumptions | Box + strip, Q-Q plots, assumption panel |
| fig09_analyst_vs_clerk | How did the two focal roles move? | Two indexed panels (no dual axis) |
| fig10_merge_attrition | How many rows/cells survive each filter and merge? | Horizontal bars, rows vs cells hatched |
| fig11_event_time_gaps_emp | When does the gap appear, given BLS panel pooling? | Gap line with CI band; tick labels show post-ChatGPT panels per year |

**Accessibility.** Okabe-Ito hues (blue, vermillion, green, grey), run through a colorblind palette validator; every color is paired with a marker, dash pattern or hatch so groups remain distinguishable in grayscale. Titles state the takeaway; axes carry units; one y-axis per panel. Interactivity is left to A7, per the assignment.

## Limitations carried forward to A6

* Sample results demonstrate the method only. The sample generator builds in an exposure-linked employment slowdown and no wage difference, so recovering both is a known-answer test of the code, not evidence. The real-data run is the first step of the data audit.
* Exposure is predicted technical potential, not adoption: all results are differential associations (`docs/A5_RESEARCH_DESIGN.md` §5).
* BLS suppresses 9-14% of cells per year; report balanced and unbalanced estimates and use EMP_PRSE / MEAN_PRSE for precision sensitivity.
* The cell-level change contrast is not the A3 estimator; A6 adds occupation × industry and industry × year fixed effects and event-time coefficients.
* NAICS vintage changes across releases (see `docs/PIPELINE.md`) would appear as unbalanced cells.
