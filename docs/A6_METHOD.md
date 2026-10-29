# A6 Method: Fixed-Effects Estimation of Exposure-Linked Employment and Wage Changes

BUS 751 · Assignment 6 (Analytics Engine & Modeling) · Pathway 2 (research-oriented) · Miguel L. Ferguson II

> **Data status.** All numbers in the A6 documents come from the **synthetic sample** (seed 751), whose generator plants a known employment effect and no wage effect. They test the method; they are not findings about real occupations. The same command produces the real-data version after an authorized raw build (`docs/DATA_ACCESS.md`).

## 1. Question, estimand, unit

**Question (A3).** Did occupations with higher predicted GenAI task exposure see different employment and wage changes after ChatGPT's November 2022 release, relative to less-exposed occupations in the same industry?

**Unit of analysis.** Detailed 2018-SOC occupation *o* × 4-digit NAICS industry *i* × May reference year *t*, 2021-2025: one published OEWS estimate per row (`v_analysis_panel`, A4). The estimation sample is every row with a published outcome and an exposure score, after singleton cells are dropped (572 rows, 124 cells, 19 occupations for employment on the sample).

**Specification (A3, unchanged).**

log *Y*<sub>oit</sub> = α<sub>oi</sub> + δ<sub>it</sub> + β · (Exposure<sub>o</sub> × Post<sub>t</sub>) + ε<sub>oit</sub>

| Term | Meaning | Why it is there |
|---|---|---|
| *Y* | total employment, or mean annual wage (separate models) | the two A3 outcomes; never combined |
| α<sub>oi</sub> | occupation-by-industry (cell) effect | removes every fixed difference between cells (size, pay level, occupation mix) |
| δ<sub>it</sub> | industry-by-year effect | removes every shock common to an industry in a year; makes the comparison within industry and year, the A5 comparison group in model form |
| Exposure<sub>o</sub> | Eloundou et al. (2024) occupation exposure, standardized across occupations (`exposure_z`) | β is per 1 SD of exposure (0.257 of the task share on the sample) |
| Post<sub>t</sub> | 1 for May 2023 onward | first May estimate with any post-ChatGPT survey panel |

**Estimand.** β is the post-2022 change in log outcome for an occupation with 1 SD higher exposure, relative to less-exposed occupations in the same industry and year. ×100 it is approximately a percentage-point difference in growth. Exposure measures *technical potential*, not adoption, so β is a **differential association**, not an effect of GenAI use (`docs/A5_RESEARCH_DESIGN.md` §5).

**Why this method fits the question.** The question is a before/after contrast in a continuous, time-invariant treatment intensity, observed in a short panel of cells. Two-way fixed effects with an exposure × post interaction is the difference-in-differences estimator for that design. It is not a prediction problem: there is no held-out target to score, so the research pathway's diagnostics (pre-period check, comparison specifications, robustness, calibrated uncertainty) replace a train/test split. Treatment timing is common to all units (one release date), so the known problems of staggered-adoption TWFE do not arise.

## 2. Variable construction (`oews_model.analysis.model_frame`)

| Variable | Definition | Source |
|---|---|---|
| `log_emp`, `log_wage` | log of `tot_emp`, `a_mean` where published and > 0 | A4 fact table via `oews_eda.data.load_panel` |
| `exposure_z` | occupation exposure, mean 0, SD 1 across occupations | A4 `occupation_exposure` |
| `exp_post` | `exposure_z` × 1[year ≥ 2023] | A3 primary |
| `exp_post_delayed` | `exposure_z` × 1[year ≥ 2024] | A3 delayed post |
| `exp_share` | `exposure_z` × share of the six pooled OEWS panels collected after ChatGPT (0, 0, 1/6, 1/2, 5/6) | `oews_eda.data.OEWS_VINTAGE` (A5) |
| `exp_y2021`, `exp_y2023`-`exp_y2025` | `exposure_z` × year dummy, 2022 omitted | A3 event study |
| `exp_placebo` | `exposure_z` × 1[year = 2022], estimated on 2021-22 only | placebo timing |
| `jz_post` | standardized Job Zone × post | preparation control |
| `analyst_post`, `clerk_post` | focal-occupation dummy × post | descriptive finance contrast |
| `indyear`, `cell_id` | fixed-effect ids | — |

Suppressed (`**`) or top-coded (`#`) values stay missing; they are never imputed. Every variable is built from the A4 database at run time, so the raw build reuses the code unchanged.

## 3. Estimation (`oews_model.estimate`)

Both sets of fixed effects are absorbed by alternating projections (the method behind reghdfe and fixest) and β is estimated by OLS on the demeaned data (Frisch-Waugh-Lovell). Cells observed once are dropped first; they are fit perfectly by their own effect and add no information. `tests/test_model.py` checks that the absorbed estimate equals dummy-variable OLS to 1e-9.

## 4. Uncertainty

Exposure varies only across occupations, so errors are clustered by **occupation** (A3). With 19 clusters, three methods are reported for each headline coefficient:

| Method | What it does | Role |
|---|---|---|
| CR1 | cluster-robust sandwich with G/(G−1)·(n−1)/(n−k); t with G − 1 df; cell effects are nested in occupations and do not count toward k | conventional reference |
| Wild cluster restricted bootstrap (WCR) | null imposed; residuals multiplied by one Webb six-point weight per occupation; 9,999 draws; CI by test inversion | **primary interval and p-value** |
| Randomization inference (RI) | exposure scores reassigned at random across occupations (4,999 draws); p = (count + 1)/(draws + 1) | assumption-light check of the sharp null |

Why WCR is primary: the Monte Carlo in `docs/A6_EVALUATION_REPORT.md` §2 shows that with this panel's 19 clusters CR1 rejects a true null about 12.5% of the time at the 5% level, while WCR (7.0%) and RI (5.5%) are close to nominal. The practical-significance verdict uses the WCR interval against the A5 bar of ±1 log point per SD of exposure.

## 5. Specifications reported

| Role | Specification | Purpose |
|---|---|---|
| Comparison | Pooled OLS: exposure, post, exposure × post | simplest descriptive model |
| Comparison | Cell + year FE | textbook two-way DiD |
| Comparison | A5 High − Low within-industry gap (`reports/eda/hypothesis_tests.csv`) | descriptive baseline from A5 |
| **Main** | **Cell + industry-by-year FE (A3)** | headline β |
| Event study | exposure × year, 2022 = 0 | timing; 2021 coefficient is the pre-period diagnostic |
| Robustness | delayed post; delayed post without 2023; panel-share dose; balanced cells; excluding May 2021 (2017 NAICS); Job Zone × post | timing, composition, coding break, omitted correlate |
| Placebo | fake post in 2022, 2021-22 only | should be ≈ 0 |
| Sensitivity | leave one industry out; leave one occupation out | influence |
| Secondary outcome | the full suite for log mean wage (two-sided) | A3 H2 |
| Descriptive | analyst × post, clerk × post | finance contrast; one occupation each, so no cluster SE (kept descriptive per A3 feedback) |

## 6. Reproducing

```powershell
uv sync --extra dev
uv run oews-pipeline run          # A4: build data/processed/oews_genai.db
uv run oews-eda                   # A5: EDA outputs
uv run oews-model                 # A6: estimates, robustness, validation, fig12-14, run log (~3-4 min)
uv run oews-model simulate        # A6: Monte Carlo calibration tables (~5 min)
uv run pytest -q                  # 42 tests
uv run oews-model --verify-against reports/model/model_run_log.json
```

`notebooks/03_model.ipynb` imports `oews_model` and walks through the same steps; it defines no estimation code. Randomness (bootstrap weights, permutations, generator seeds) is seeded throughout, so every number is reproducible.

## 7. Module interface

| Module | Public interface |
|---|---|
| `estimate` | `fit(df, y, x, fixed_effects, cluster)` → `FEResult` (`table`, `coef()`, `row()`); `absorb`; `ModelError` |
| `inference` | `wild_cluster_bootstrap(res, term, B, seed)`; `randomization_inference(frame, res, build_x, n_perm, seed)` |
| `analysis` | `model_frame(panel)`; `specifications(outcome)`; `run_spec`; `event_study`; `leave_one_out`; `finance_contrast`; `practical_verdict` |
| `validation` | `closed_form`; `recovery`; `monte_carlo`; `summarize_monte_carlo` |
| `report` | `run_all(db_path, ...)` → summary dict and every artifact; `simulate(seeds)` |
| CLI | `uv run oews-model [run|simulate] [--db PATH] [--verify-against LOG]`; exit 2 with a message on a missing database, failed quality gate or inestimable specification |

The A7 dashboard reads `reports/model/*.csv` and `model_summary.json`; nothing needs to be re-estimated at view time.
