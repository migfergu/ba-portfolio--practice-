# Executive Summary: GenAI Exposure and Finance-Sector Employment and Pay

BUS 751 · Assignment 5 (Exploratory Data Analysis) · Miguel L. Ferguson II · October 2026

> **Data status.** Every number below comes from the project's **synthetic sample**: invented values in the real BLS file layouts, with a built-in pattern used to test the code. The numbers show what the analysis reports and how to act on it; they are not facts about real occupations. The same code produces the real-data version after an authorized run on the licensed BLS files (`docs/DATA_ACCESS.md`, "Full-data verification"). Licensed data are never stored in this repository.

## The question (from A3)

After ChatGPT's release in November 2022, did occupations whose tasks GenAI *could* most affect see different **employment levels** or **average pay** than less-exposed occupations in the same industry? The study covers about 20 occupations across 10 finance, professional-services and comparison industries, May 2021-May 2025, with financial and investment analysts and bookkeeping clerks as focal roles.

"Exposure" is a published estimate of each occupation's *technical potential* for GenAI. It does not show that employers used it. Every finding below is therefore a **difference between more- and less-exposed jobs**, not a measured impact of GenAI.

## Bottom line

**On the sample, employment in highly exposed occupations grew about 2.7 percentage points less than in less-exposed occupations in the same industries after 2022, a gap large enough to matter for workforce plans. Average pay showed no detectable difference, though a small pay gap cannot yet be ruled out.**

## What the analysis shows (sample run)

1. **Slower employment growth in exposed occupations.** Within the same industry, employment in high-exposure occupations grew about 2.7 points less than in low-exposure occupations between 2021-22 and 2023-25 (Figures 4 and 8). The gap clears our pre-set bar of 1 point for "large enough to matter": its whole uncertainty range is −4.4 to −1.3 points. Controls for job preparation and starting pay do not remove it (Figure 7).
2. **The gap shows up as post-ChatGPT survey data accumulate.** Each BLS May estimate blends six survey rounds from three years, so May 2023 contains only one round collected after ChatGPT. Correspondingly, the gap is about zero in 2023, −2.4 points in 2024 and −5.3 points in 2025 (Figure 11). This timing is what BLS's data construction alone would produce, so it should not be read as proof that adoption is speeding up.
3. **No detectable pay difference.** Average annual pay rose about 8.5% in both groups. The uncertainty range (about −1.2 to +1.0 points) still includes a 1-point gap in either direction, so the right reading is "no pay difference detected yet", not "pay is unaffected".
4. **Exposure is its own dimension.** An occupation's exposure is almost unrelated to how much preparation it requires or how well it pays (Figure 6). High-skill or high-pay roles are not automatically low-exposure.
5. **Analysts vs. clerks.** Both focal roles are at the high-exposure end. With only two or three comparable industries each, Figure 9 is context only; the formal comparison comes in A6.

## What a decision-maker can do with this

| Audience | Action now | Revisit when |
|---|---|---|
| Finance workforce planners | Treat exposure as a planning variable. Build a scenario with ~2-3 points slower headcount growth for highly exposed roles (analysts, accountants, data entry, developers) next to the baseline plan, rather than assuming either no change or job losses. | The real-data run confirms or rejects the sample-size gap |
| Talent and L&D leaders | Prioritize reskilling in exposed roles toward their less-exposed tasks; this holds whatever the eventual cause of the gap. | A6 shows whether preparation level changes the gap |
| Compensation teams | Do not apply a GenAI discount to pay benchmarks; no pay difference is detected. Keep monitoring, since a ~1-point difference is not ruled out. | The May 2026 release adds data |
| Program and policy readers | Monitor exposed occupations as a group across skill and pay bands. | Each new BLS release |

## How much weight to put on it

* **Direction: moderate. Size: provisional.** The employment gap holds across five checks: two-group test, rank-based test, occupation-level resampling, occupation-level permutation, and regression with industry controls. A "before-period" check (2021 vs 2022) shows no gap, which supports the comparison, though that check is imprecise.
* **Not a causal estimate.** Other 2023-24 shocks that hit exposed occupations harder (interest rates, the tech-hiring slowdown) could explain part of the gap. Comparing within industries removes industry-wide shocks but not occupation-specific ones. `docs/A5_RESEARCH_DESIGN.md` §5 lists the assumptions a causal claim would need.
* **Coverage.** BLS withholds 9-14% of occupation-industry cells each year for confidentiality or reliability. Results describe the cells BLS publishes.
* **Sensitivity.** When the first year (May 2021, which used an older industry coding) is dropped, the gap stays significant but its range now reaches inside the 1-point bar.

## What these data cannot tell you

Whether employers adopted GenAI; whether slower growth came from fewer hires or more departures (BLS reports headcount, not flows); what happened to individual workers; hours, bonuses or benefits; or regional and firm-level patterns.

## Next steps

1. **Real data:** run the pipeline on the licensed files, verify input checksums, commit only the aggregate outputs and run log.
2. **A6 model:** the A3 specification (occupation-by-industry and industry-by-year controls, errors grouped by occupation), year-by-year estimates with 2022 as reference, a version timed by the share of post-ChatGPT survey rounds, and the analyst-vs-clerk comparison.
3. **A7 dashboard:** interactive versions of Figures 4, 9 and 11 for finance-workforce readers.

*Full analysis: `notebooks/02_eda.ipynb` · Figures: `reports/figures/` · Method: `docs/EDA_METHODOLOGY.md` · Design notes: `docs/A5_RESEARCH_DESIGN.md`*
