# Executive Summary: GenAI Exposure and Finance-Sector Jobs

BUS 751 · Assignment 5 (Exploratory Data Analysis) · Miguel L. Ferguson II · October 2026

> **Read this first.** The numbers below come from the project's **synthetic sample** (invented values in the real file layouts), which is what the public repository builds. They show what the analysis will report and how to read it, not facts about real occupations. Running `uv run oews-pipeline run --source raw` and then `uv run oews-eda` refreshes every number in `reports/eda/eda_summary.json` and every figure on the real BLS data; the sentences below are then updated from that file.

## The question

After ChatGPT's release in late 2022, did jobs whose tasks are most exposed to generative AI grow or pay differently from less-exposed jobs? We compare about 20 occupations across 10 finance, professional-services and comparison industries, May 2021 through May 2025, with a focus on **financial and investment analysts** and **bookkeeping and accounting clerks**.

## Bottom line

**Headcount in highly exposed jobs grew more slowly after 2022, and the gap is widening; pay has not moved.** Plan for slower hiring growth in GenAI-exposed roles now, and do not cut pay benchmarks on GenAI grounds yet.

## What we found

1. **Exposed jobs added staff about half as fast.** From 2021-22 to 2023-25, employment in high-exposure occupation-industry groups grew about 2.7%, against about 5.6% in low-exposure groups (Figure 4). The gap holds after accounting for the industry, the training a job requires, and its starting pay, and it passes every statistical check we applied (Section 5 of the notebook). A one-step increase in exposure (one standard deviation) goes with about 2.6 points less employment growth.
2. **The gap is getting bigger, not fading.** Measuring "after" from 2024 instead of 2023 enlarges the gap from about 2.8 to about 4 points, and the trend chart (Figure 5) shows the low-exposure group pulling further ahead each year. That pattern fits a slow rollout of the technology rather than a one-time shock.
3. **Pay has not diverged.** Average wages rose about 8.5% in both groups; there is no measurable difference (Figure 4 companion results, notebook Section 5.2). So far, exposure shows up in *how many* people are hired, not in *what they earn*.
4. **Exposure is its own risk factor.** How exposed a job is has almost nothing to do with how much training it requires or how well it pays (Figure 6). "High-skill" or "well-paid" does not mean "safe".
5. **Analysts versus clerks.** Both focal roles sit at the high-exposure end. With only two or three comparable industries each, we describe their paths (Figure 9) but do not draw conclusions; that comparison is tested formally in the next phase.

## What to do with this

| Audience | Action |
|---|---|
| Workforce planners in finance | Build slower headcount growth into plans for exposed roles (analysts, accountants, data entry, developers); revisit yearly, because the effect is still growing. |
| Talent and L&D leaders | Shift development budgets toward the tasks GenAI does not cover in exposed roles, rather than toward hiring more people into the same task mix. |
| Compensation teams | Keep current pay benchmarks; there is no evidence of a GenAI-related wage discount yet. Re-check when the 2026 data arrive. |
| Program and policy readers | Track exposed occupations as a group, not by skill level or pay band, since exposure cuts across both. |

## How confident should you be?

* **Moderately, as a direction.** The pattern is consistent across five separate checks, including ones that do not treat each industry cell of the same occupation as independent evidence.
* **It is an association, not proof of cause.** Other forces that hit exposed jobs after 2022 (interest rates, the tech-sector slowdown) could contribute. The next phase (A6) adds year-by-year comparisons and industry-by-year controls to narrow this.
* **Some small groups are hidden.** BLS suppresses 9-14% of occupation-industry cells each year for confidentiality, so the smallest groups are under-represented.

## Next steps

1. Load the real BLS files and refresh all results (one command each).
2. A6: estimate the full model from the A3 proposal (occupation-by-industry and industry-by-year controls, standard errors grouped by occupation), year-by-year effects with 2022 as the reference, and the analyst-versus-clerk comparison.
3. A7: turn Figures 4, 5 and 9 into an interactive dashboard for finance-workforce readers.

*Figures: `reports/figures/`. Full analysis: `notebooks/02_eda.ipynb`. Method: `docs/EDA_METHODOLOGY.md`.*
