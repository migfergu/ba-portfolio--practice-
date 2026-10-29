# A5 Research-Design Notes: Responses to the A4 Feedback

This file answers the questions raised in the A4 review and points to the code and outputs that carry each answer. All counts are from the **committed synthetic sample**; the same code produces the real-data counts after an authorized `--source raw` run (see "Full-data verification" in `docs/DATA_ACCESS.md`).

## 1. What is one row, and which source supplies each field?

**One row = one detailed 2018-SOC occupation × one 4-digit NAICS industry × one May reference year (2021-2025)**, national, all ownerships, from the BLS OEWS national industry-specific estimates (`nat4d`). Key: `(soc_code, naics_code, year)`. The EDA collapses rows to **cells** (occupation × industry) for pre/post comparisons. Machine-readable: `oews_eda.data.panel_definition()` → `reports/eda/panel_definition.csv`.

| Role | Field | Source | Meaning and limits |
|---|---|---|---|
| Outcome 1 | `tot_emp` → `log_emp` | OEWS `TOT_EMP` | Employment **level** (a stock). Not hires, separations, or hours |
| Outcome 2 | `a_mean` → `log_wage` | OEWS `A_MEAN` | Mean annual wage of incumbents. Changes when the mix of workers changes |
| Precision | `emp_prse`, `mean_prse` | OEWS `EMP_PRSE`, `MEAN_PRSE` | Relative standard errors, for sensitivity checks |
| Flags | `emp_suppressed`, `wage_suppressed`, `wage_topcoded` | OEWS `**`, `*`, `#` | Kept as NULL + flag; never imputed |
| Exposure | `exposure_main`, `exposure_z` | Eloundou et al. (2024) `occ_level.csv`, `dv_rating_gamma` | **Predicted technical potential** (share of tasks exposed directly or with complementary software). Fixed per occupation. Not observed adoption |
| Control / moderator | `job_zone_mean` | O*NET 27.0 Job Zones (Aug 2022, before ChatGPT) | Preparation level 1-5 |
| Timing | `post`, `post_delayed`, `post_panel_share` | `config/sources.toml`; BLS technical notes | See section 4 |

**The two outcomes stay separate.** They are tested, modeled and plotted separately (`d_log_emp*` vs `d_log_wage*`), each with its own hypothesis: one-sided H1 for employment, two-sided for wages. They are never combined into a wage bill. A mean-wage change in a cell that is losing jobs can come from *who* stays rather than from pay rates, so wage results are read as "mean pay of the remaining workforce".

## 2. Which crosswalks make each join valid?

`oews_eda.data.CROSSWALKS` → `reports/eda/crosswalks.csv`.

| Join | Codes | Rule | Audit |
|---|---|---|---|
| Exposure → panel | O*NET-SOC 8-digit → 2018 SOC 6-digit | Drop the `.NN` suffix; average when several O*NET codes map to one SOC | `occupation_exposure.n_onet_codes` |
| Job Zones → panel | O*NET-SOC 8-digit → 2018 SOC 6-digit | Same; mean and max | `occupation_preparation.n_onet_codes` |
| OEWS industries | 4-digit NAICS, padded to 6 | **May 2021 uses 2017 NAICS; May 2022 onward use 2022 NAICS** (BLS technical notes) | Changed codes show up as unbalanced cells; robustness test drops 2021 |
| OEWS occupations | 2018 SOC, every panel year | May 2021 is the first release based entirely on 2018-SOC survey data, so no SOC crosswalk is needed within 2021-2025 | `dim_occupation.soc_vintage` |

## 3. How many cells survive each merge and filter?

`oews_eda.data.attrition_table()` → `reports/eda/attrition.csv`, Figure 10. On the sample:

| Stage | Count |
|---|---|
| OEWS rows read (5 files) | 757 rows |
| In panel grain (detailed occupation × 4-digit industry; 105 aggregate rows filtered) | 652 rows |
| Passed validation → fact table (7 quarantined) | 645 rows |
| Occupation has an exposure score (1 occupation unmatched) | 615 rows |
| Employment not suppressed (model-ready) | 572 rows |
| Cells with ≥ 1 pre and ≥ 1 post year | 123 cells |
| Cells observed in all 5 years (balanced) | 87 cells |

Suppression removes 9-14% of rows per year (Figure 1). Trend figures use the balanced 87 cells; tests use the 123 cells with both periods, and `test_attrition_reconciles` checks that the counts add up.

**On duplicates (A4 note).** OEWS rows are published survey estimates with no transaction identifier. An "exact duplicate" is an identical source row repeated in a file, not evidence of a duplicated underlying transaction. `docs/QUALITY_REPORT.md` §4 and the data dictionary now say so.

## 4. OEWS methodology, pooling, and event timing

Facts from the BLS technical notes for each May release (`oews_eda.data.OEWS_VINTAGE`):

| May estimate | Six panels pooled | Panels after ChatGPT (30 Nov 2022) | Method | NAICS |
|---|---|---|---|---|
| 2021 | Nov 2018 - May 2021 | 0/6 | MB3, first release | 2017 |
| 2022 | Nov 2019 - May 2022 | 0/6 | MB3 | 2022 |
| 2023 | Nov 2020 - May 2023 | 1/6 | MB3 | 2022 |
| 2024 | Nov 2021 - May 2024 | 3/6 | MB3 | 2022 |
| 2025 | Nov 2022 - May 2025 | 5/6 | MB3 | 2022 |

*The 2024 row follows the same six-panel pattern as the releases checked directly.*

Consequences:

* **The methodology break is avoided by design.** MB3 began with the May 2021 estimates, so every year in the panel uses the same estimation method and 2018 SOC. Comparing with pre-2021 releases would mix methods; the panel does not.
* **BLS does not encourage OEWS time-series analysis.** Pooling three years of panels means consecutive estimates share most of their data. The design therefore relies on a *differential* comparison (high- vs low-exposure occupations in the same industry and year) rather than on year-to-year changes in levels. Common changes in survey practice difference out.
* **Pooling dilutes and delays any post-2022 pattern.** May 2023 contains only one post-ChatGPT panel. A "post = 2023+" dummy is mostly pre-period data, so it biases the gap toward zero. On real data, a gap that grows with the post-ChatGPT panel share is therefore **not by itself evidence of gradual adoption**; pooling alone would produce it. The synthetic sample cannot show this: its generator plants an effect proportional to (year − 2022) and does not simulate pooled panels, so Figure 11's sample values (+0.07 pp in 2023, −2.4 pp in 2024, −5.3 pp in 2025) reflect the planted ramp plus noise. The near-zero 2023 value is an unusual seed draw, not a code defect (`docs/A6_EVALUATION_REPORT.md` §1). A6 reports event-time coefficients and a specification that uses `post_panel_share` as the timing variable.
* **NAICS 2017 → 2022 sits inside the pre-period** (2021 → 2022). The test that drops 2021 keeps the employment result (gap −2.5 pp, p < 0.001), but its cluster CI reaches inside the ±1 pp band (*detectable, size uncertain*). This sensitivity is reported, not hidden.
* **Is the post period long enough?** It has three nominal post years, but only the May 2025 estimate is mostly post-ChatGPT data (5 of 6 panels), and May 2024 is half. That is enough to describe a differential pattern but not to separate it cleanly from other 2023-24 shocks that also loaded on exposed occupations (interest rates, the tech-hiring slowdown). Industry-by-period comparisons absorb shocks common to an industry but not occupation-specific ones. This is the main reason results stay associations.

## 5. Exposure is technical potential, not adoption

The Eloundou et al. score measures how much of an occupation's task content GenAI *could* affect. It says nothing about whether employers adopted it. All results are therefore phrased as a **differential association**: occupations with higher predicted exposure had different post-2022 outcomes than lower-exposure occupations in the same industry and period. Figure titles, test interpretations (`GroupTestResult.interpretation` ends with this caveat) and the executive summary use that wording.

**Comparison group.** Lower-exposure occupations *in the same 4-digit industry* over the same period. The primary test uses `d_log_emp_wi`, the cell's change minus its industry's mean change. This is the long-difference analogue of the A3 industry-by-year fixed effects, so industry-wide shocks cancel.

**Event timing.** 2022 is the reference year (last estimate with no post panels). 2023 is the first nominal post year; 2024+ is the delayed post; `post_panel_share` is the dose.

**Pre-trend evidence.** The 2021 → 2022 placebo (both years pre-ChatGPT) shows no detectable gap (−0.5 pp, p = 0.50). Its CI is wide, [−2.1, +0.9] pp, so parallel pre-trends are *not contradicted* but *not proven*. With only two pre-period years, this is a weak test, and it is stated as one.

**What a causal reading would additionally require.**
1. Parallel trends: without GenAI, high- and low-exposure occupations within an industry would have followed the same path.
2. No concurrent shock that differs by exposure, for example a tech or finance downturn concentrated in exposed occupations.
3. Exposure works as a proxy for treatment intensity, and actual adoption rises with it. This cannot be checked without adoption data.
4. No spillovers: low-exposure occupations are not themselves affected, for example by reallocation of tasks.
5. Stable cell composition: suppression and pooling do not change which establishments enter each cell in ways related to exposure.
6. No anticipation before the release.

## 6. What counts as a practically meaningful estimate?

The analysis pre-sets a **minimum meaningful gap of 1 percentage point** of employment or wage growth over the post period (`report.PRACTICAL_THRESHOLD = 0.01` log points; on the sample, roughly half a year of typical growth). Each test classifies its occupation-cluster CI against that band with `inference.practical_significance`:

| Test (sample) | Gap | Cluster 95% CI (pp) | Verdict |
|---|---|---|---|
| Employment, within industry (primary H1) | −2.7 pp | [−4.4, −1.3] | practically meaningful |
| Employment, delayed post (2024+) | −3.9 pp | [−5.8, −2.3] | practically meaningful |
| Employment, excluding 2021 (NAICS change) | −2.5 pp | [−4.5, −1.0] | detectable, size uncertain |
| Wages, within industry (two-sided) | +0.02 pp | [−1.2, +1.0] | inconclusive |
| Placebo 2021 → 2022 employment | −0.5 pp | [−2.1, +0.9] | inconclusive |

The wage result shows why this matters. "Not significant" (p = 0.97) does **not** mean "no wage effect". The CI still allows a gap of about 1 pp in either direction, so the data cannot rule out a small but meaningful wage difference. The summary says "no detectable difference; a 1-point gap cannot be ruled out", not "pay is unaffected".

## 7. What the database fields cannot support

* Any **causal** claim that GenAI caused job loss, displacement, augmentation or productivity change (section 5).
* Anything about **employer adoption or use** of GenAI; there is no adoption field.
* **Hiring, layoffs or worker flows.** `TOT_EMP` is a level; a slower-growing level can come from fewer hires or more exits, and the data cannot tell which.
* **Individual workers' outcomes** such as earnings changes for a given person, re-employment, or occupational switching.
* **Hours, part-time status, or total compensation** (benefits, bonuses).
* **Firm-level or regional patterns**; the panel is national × industry.
* **Small occupation-industry cells** that BLS suppresses; results describe the cells BLS publishes.

## 8. Note on the synthetic sample

The sample generator (`src/oews_pipeline/sample_data.py`, A4) deliberately builds in an exposure-linked employment slowdown after 2022 and no wage difference. Recovering those two patterns is a **known-answer test** of the EDA code: it shows the module finds a pattern that is present and does not invent one that is absent. It is not evidence for the hypothesis. Real conclusions wait for the licensed-data run.
