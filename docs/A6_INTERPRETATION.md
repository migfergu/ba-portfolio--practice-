# A6 Research Interpretation

BUS 751 · Assignment 6 · Miguel L. Ferguson II

> **Read this first.** Every number below is from the synthetic sample, whose generator plants a known employment effect, no wage effect, and no OEWS pooling. So this document has two layers: what the sample run shows about the **method**, and, in the boxed paragraphs, what the same section will say **once the authorized real-data run is in**. No sentence here describes the real labor market yet.

## 1. The question and what the design can answer

**A3 question.** After ChatGPT's release, did occupations with higher predicted GenAI exposure see different employment and wage changes than less-exposed occupations in the same industry?

**Level the design supports.** A differential association: how the post-2022 path of more-exposed occupations differed from less-exposed ones in the same industry and year. It does not identify the effect of GenAI *use* (exposure is technical potential, not adoption), and it cannot separate GenAI from other 2023-25 shocks that loaded on the same occupations (interest-rate-sensitive finance hiring, the tech-hiring slowdown). That is the **inferential boundary**: the estimate is a well-measured contrast, not a causal effect.

## 2. Employment (H1: β < 0)

**Sample run.** β = −0.026 log points per 1 SD of exposure (wild-cluster-bootstrap 95% CI −0.040 to −0.016; bootstrap p < 0.001; randomization p < 0.001). In plain terms, an occupation 1 SD more exposed grew about **2.6% less** after 2022 than a less-exposed occupation in the same industry; moving from the 25th to the 75th percentile of exposure corresponds to about **2.1% less** growth. The whole interval lies beyond the 1-point practical bar, the sign and size survive every robustness check (−0.024 to −0.035 across timing, sample and control variants), and no single industry or occupation drives it.

**What that means for the method.** The generator planted β ≈ −0.030. The estimate is 1.6 sampling SDs from it, the noise-free run recovers it to 0.0001, and the inference that the report leads with (wild bootstrap and randomization) rejects a true null about 5-7% of the time. The engine therefore finds a planted effect of this size, does not invent one when none is planted, and reports uncertainty honestly. It does **not** mean employment in exposed occupations fell in the real economy.

> **On real data this section will state:** the estimated β with its bootstrap interval; whether the interval clears the 1-point bar (practically meaningful), sits inside it (negligible), or straddles it (inconclusive); the interquartile translation; and whether the robustness table agrees. A negative, practically meaningful β would support H1 as an association; it would still not show displacement.

## 3. Timing

**Sample run.** Event-time coefficients are about 0 in 2023, −0.025 in 2024 and −0.042 in 2025. The 2021 coefficient is small and not distinguishable from zero, and a placebo with a fake 2022 "post" finds nothing. On the sample the growing path is the **planted ramp** (the generator adds one more step each year) plus a lucky 2023 draw (`docs/A6_EVALUATION_REPORT.md` §1.3). The generator does not simulate how BLS pools survey panels, so the sample says nothing about pooling.

> **On real data this section will state:** whether the event-time path rises with the share of post-ChatGPT survey panels in each May estimate (1/6, 1/2, 5/6). A path that tracks that share is what BLS's pooling alone would produce, so it must not be read as adoption accelerating. The panel-share specification gives the gap once every pooled panel is post-ChatGPT; the next May releases (more post panels) are the real test of timing.

## 4. Wages (two-sided)

**Sample run.** β = +0.001 (95% CI −0.005 to +0.005). The interval is inside ±1 log point, so a pay difference of practical size is ruled out on the sample, matching the generator, which plants none.

> **On real data this section will state:** the wage β and interval against the bar. Mean wage is the pay of incumbents, so a null wage result alongside an employment gap would mean slower headcount growth without a measurable pay discount for those employed, not "no effect on workers".

## 5. Financial analysts vs. bookkeeping clerks (descriptive)

Both focal roles sit near the top of the exposure distribution. After the exposure-predicted path is accounted for, analysts' employment is about +0.7% and clerks' about +1.5% off that path on the sample. Each role is one occupation, so no standard error exists and these are context, not tests (as the A3 feedback required). Whether GenAI complements analysts' tasks while substituting for clerks' cannot be answered with occupation-level OEWS data.

## 6. Limitations

1. **Association, not effect.** Exposure is potential, not use; other occupation-specific shocks in 2023-25 cannot be separated from GenAI.
2. **Few clusters.** 19 occupations. Handled with wild-cluster and randomization inference (calibrated in the Monte Carlo), but power for heterogeneity (by role, by job zone) is low.
3. **Short pre-period.** One pre-period coefficient (2021); the consistent-method window starts with May 2021, so parallel trends cannot be tested strongly.
4. **OEWS construction.** Each May estimate pools three years of survey panels, so consecutive years share data and any change appears gradually; estimates are levels (no hires or separations); suppression removes 9-14% of cells per year, so results describe published cells.
5. **Coding breaks.** May 2021 uses 2017 NAICS; the result survives dropping it on the sample, and the check is kept for the real run.
6. **Not yet covered.** Employment-weighted estimates, alternative exposure measures (Eloundou β or human ratings), and regional or firm detail.
7. **Synthetic data.** Every number in this document comes from test data; the substantive answer requires the authorized real-data run.

## 7. Research implication

If the real-data run reproduces a negative, practically meaningful β that survives the bootstrap and robustness checks, the defensible conclusion is: *more GenAI-exposed occupations grew more slowly than less-exposed ones in the same industries after 2022*, with the size stated per SD of exposure and the timing read against OEWS pooling. That is evidence worth monitoring with each new release and worth testing with adoption or task-level data; it is not evidence that GenAI displaced workers. If β is negligible or inconclusive, the right conclusion is that the first post-ChatGPT OEWS releases show no detectable differential, which, given pooling, is not evidence of no change.

For the A7 dashboard, the readers are finance workforce planners and program leaders; the views come straight from `reports/model/` (specification forest, event study, leave-one-out, wage vs employment) with the synthetic-data banner kept until the real run replaces the files.
