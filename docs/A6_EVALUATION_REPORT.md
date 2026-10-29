# A6 Evaluation Report: Validation, Diagnostics, Comparison and Robustness

BUS 751 · Assignment 6 · Miguel L. Ferguson II

> **Synthetic sample.** Every estimate below is from the seed-751 synthetic sample. The generator plants `employment × [1 − 0.06 (exposure − 0.6)(year − 2022)]` from 2023 and **no wage effect**, and it does **not** simulate OEWS panel pooling. Sections 1-2 use that known answer to validate the code and the inference; sections 3-6 show what the report will contain on real data. Tables: `reports/model/`. Figures: `reports/figures/fig12-fig14`.

## 1. Known-answer validation (A5 feedback items 1 and 3)

The A5 feedback asked for (1) a quantified known-answer test with a tolerance that fails when estimates drift and (3) an explanation of why the 2023 gap was ~0 when the generator plants a 2023 effect. Both are answered by separating two questions that a single noisy run cannot tell apart.

**Question A: is the code right?** `generate(emp_noise_sd=0)` removes all randomness from employment while consuming the random stream identically, so every other value is unchanged. On that panel each statistic must equal the **oracle**: the same estimator applied to the planted log effect on the same surviving cells. Only integer rounding of headcounts separates them.

**Question B: is the committed seed's estimate plausible?** 200 further seeds (752-951) give the sampling spread of each statistic in a 19-occupation, ~130-cell panel.

### 1.1 Expected values derived from the generator

* **fig04 slope.** fig04 regresses each cell's d_log_emp = mean(2023-25 log emp) − mean(2021-22 log emp) on exposure. With ln(1 − a·x·k) ≈ −a·x·k, a = 0.06 and k = year − 2022 averaging (1 + 2 + 3)/3 = 2 in the post years, the slope is −2a = −0.12 per unit of exposure, i.e. **−1.20 points per +0.1 exposure** (`known_answer.closed_form_slope`).
* **A6 β.** The same logic per 1 SD of exposure: −0.06 × 2 × 0.257 = **−0.0309** log points; event-time coefficients −0.0154 × (t − 2022) (`validation.closed_form`).

### 1.2 Results (`reports/model/known_answer_eda.csv`, `model_recovery.csv`)

| Statistic | Closed form | Oracle | Noise-free estimate | Code error | Code tolerance | Seed 751 | Seed SD (200) | Seed-751 percentile |
|---|---|---|---|---|---|---|---|---|
| fig04 slope (pts per +0.1) | −1.20 | −1.18 | −1.16 | +0.02 | ±0.10 | −1.00 | 0.11 | 94th |
| fig11 gap 2023 (pts) | — | −1.79 | −1.79 | −0.00 | ±0.25 | **+0.07** | 0.77 | **99.5th** |
| fig11 gap 2024 (pts) | — | −3.68 | −3.69 | −0.01 | ±0.25 | −2.39 | 0.76 | 98th |
| fig11 gap 2025 (pts) | — | −5.70 | −5.71 | −0.01 | ±0.25 | −5.32 | 0.87 | 75th |
| A6 β, main | −0.0309 | −0.0304 | −0.0305 | −0.0001 | ±0.001 | −0.0262 | 0.0026 | — |
| A6 event 2023 | −0.0154 | −0.0152 | −0.0153 | −0.0000 | ±0.002 | −0.0049 | — | — |

*Seed SD and percentile columns: 200 seeds, `known_answer_seeds.csv`. The A6 β seed SD comes from the Monte Carlo (§2).*

**How the tolerances were set.** The code tolerances are about four times the largest rounding error observed (0.02 points for the slope, 0.01 for any gap, 0.0001 for β) and far smaller than any plausible defect: an effect that starts a year late moves the 2023 gap by ~1.8 points and the slope by ~0.4. The sampling band is ±3 seed SDs around the noise-free value. Both are pinned in `tests/test_known_answer.py` and `tests/test_model.py`, which fail if an estimate drifts outside them. Two **mutation tests** shift the planted effect by a year and confirm the checks then fail; a known-answer test that passes on a bug is not doing its job.

**Why the oracle differs from the closed form (−1.18 vs −1.20).** The closed form drops the second-order log term, and the EDA groups by the Eloundou-file exposure (an average over O*NET sub-codes) rather than the generator's own value. Both are documented approximations, not defects; the bound is 0.05 points.

### 1.3 What happened to 2023

Traced through each candidate the feedback listed:

| Candidate | Check | Result |
|---|---|---|
| Generator | `planted_effect(e, 2023)` = 1 − 0.06(e − 0.6) | applies one unit in 2023, as intended |
| Pipeline | noise-free run → database → EDA | 2023 gap −1.79 vs oracle −1.79 |
| Change definition / 2022 reference | same run; `cell_year_changes` subtracts each cell's own 2022 value | correct; 2022 gap is exactly 0 |
| Median split | same run; groups by occupation, not by cell | correct |
| **Sampling noise** | 200 seeds | 2023 gap mean −1.90, SD 0.77; seed 751's +0.07 is exceeded by 1 seed in 200 |

**Conclusion: not a code defect.** Seed 751 drew an unusually favorable 2023 for high-exposure cells. Part of the shortfall is shared by every year, because all gaps are measured from the same noisy 2022 reference (seed 751 also sits above the median in 2021, at the 77th percentile, and in 2024, at the 98th); the rest is the 2023 draw itself. The event-time design has one reference year, so one noisy reference moves the whole path; the A6 model, which averages both pre years, is less exposed to this (seed-751 β is at −0.0262 against a true −0.0304, about 1.6 seed SDs).

## 2. Is the inference trustworthy with 19 clusters? (Monte Carlo)

`uv run oews-model simulate` rebuilds the database and refits the main model on 200 seeds with the planted effect and 200 with no effect (`reports/model/monte_carlo_summary.csv`).

| Scenario | Mean truth | Mean β̂ | Bias | SD of β̂ | Mean CR1 SE | CR1 95% coverage | Reject at 5%: CR1 | WCR | RI |
|---|---|---|---|---|---|---|---|---|---|
| No effect | 0 | −0.0001 | −0.0001 | 0.0026 | 0.0022 | 87.5% | **12.5%** | 7.0% | 5.5% |
| Planted effect | −0.0303 | −0.0303 | −0.0001 | 0.0026 | 0.0023 | 91.0% | 100% | 100% | 100% |

* The estimator is **unbiased** for the oracle in both scenarios.
* **CR1 standard errors are too small** (about 85-89% of the true sampling SD), so CR1 intervals under-cover and the CR1 test rejects a true null 2.5 times too often. This is the small-cluster problem the A3 design anticipated, now measured on this panel.
* **WCR and RI hold their size** (7.0% and 5.5%; with 200 draws a correctly sized test lands between about 2% and 8%). Both keep full power against the planted effect. They are therefore the headline inference; CR1 is reported for reference only.

## 3. Comparison with simpler specifications (`specifications_emp.csv`, fig13)

| Specification | β (log pts per SD) | WCR 95% CI | p (WCR) | p (RI) |
|---|---|---|---|---|
| Pooled OLS, no fixed effects | −0.0272 | [−0.063, +0.059] | 0.46 | — |
| Cell + year FE | −0.0273 | [−0.040, −0.018] | 0.001 | 0.0002 |
| **A3: cell + industry-by-year FE** | **−0.0262** | **[−0.040, −0.016]** | **0.0008** | **0.0002** |
| A5 descriptive: High − Low within-industry gap | −2.7 pts (binary groups) | cluster CI [−4.4, −1.3] pts | — | — |

The point estimate barely moves across specifications, so the fixed effects are not manufacturing the result. What they add is **precision**: pooled OLS leaves the large level differences between cells in the residual and cannot distinguish the gap from zero. Moving from year effects to industry-by-year effects changes β by 0.001, so industry-wide shocks do not drive the contrast on this sample.

## 4. Diagnostics

| Diagnostic | Result (sample) | Reading |
|---|---|---|
| Pre-period coefficient (2021 vs 2022) | +0.0050, WCR CI [−0.005, +0.011], p = 0.28 | no detectable pre-trend; one pre year gives low power, so this is a diagnostic, not proof |
| Placebo: fake post in 2022 on 2021-22 | −0.0024, WCR CI [−0.010, +0.008], p = 0.53 | no effect where none can exist |
| Event-study path (fig12) | 2023 −0.005, 2024 −0.025, 2025 −0.042 | on the sample this is the planted ramp plus the 2023 draw in §1.3, **not** evidence about OEWS pooling (the generator does not pool) |
| Leave one industry out | β from −0.0280 to −0.0243 (10 fits) | no single industry drives β |
| Leave one occupation out | β from −0.0287 to −0.0231 (19 fits) | no single occupation drives β, including the focal roles |
| Clusters, singletons | 19 occupation clusters; singleton cells dropped before estimation | small G handled by WCR/RI (§2) |
| Absorbed FE vs dummy OLS | identical β to 1e-9 | estimator implemented correctly (test) |

## 5. Robustness and sensitivity (`specifications_emp.csv`)

| Check | β | WCR 95% CI | Verdict vs ±1-pt bar |
|---|---|---|---|
| Delayed post (2024+, 2023 coded pre) | −0.0329 | [−0.045, −0.027] | practically meaningful |
| Delayed post, 2023 excluded | −0.0352 | [−0.051, −0.029] | practically meaningful |
| Dose: post-ChatGPT panel share | −0.0534 | [−0.068, −0.047] | practically meaningful |
| Balanced cells only | −0.0264 | [−0.042, −0.013] | practically meaningful |
| Excluding May 2021 (2017 NAICS) | −0.0239 | [−0.042, −0.012] | practically meaningful |
| Adding Job Zone × post | −0.0250 | [−0.039, −0.017] | practically meaningful |

All checks keep the sign and stay outside the practical bar. Two need reading with care. The **dose** coefficient is the gap once every pooled panel is post-ChatGPT, so it is larger by construction and is not comparable in size to β. The **delayed-post** estimates are larger because, on the sample, the planted effect grows each year; on real data a larger delayed-post estimate could equally reflect pooling, which is why the dose specification exists.

## 6. Wages (secondary, two-sided)

Main wage β = +0.0012, WCR CI [−0.0052, +0.0052], p = 0.49, RI p = 0.72. The whole interval is inside ±1 log point, so on the sample a wage gap of practical size is ruled out, matching the generator (no wage effect planted). Delayed-post and dose wage estimates have wider intervals that reach the bar (inconclusive), so the wage conclusion rests on the main specification.

## 7. What this evaluation does not cover

Weighting by baseline employment, an alternative exposure measure (Eloundou's β or human ratings) and an analyst-specific inference all need either more occupations or pipeline changes; they are listed as A7/real-data extensions in `docs/A6_INTERPRETATION.md`.
