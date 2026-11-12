# Final presentation: live dashboard path (9:30-10:45, 75 seconds)

One prepared user path, tied to the opening question. No page-by-page tour, no live coding.

## Before the slot

```powershell
cd migfergu-ba-portfolio-practice
uv run oews-dashboard-check          # must print OVERALL: PASS
uv run streamlit run streamlit_app.py
```

Open the app, leave it on **The answer** with Employment + Wild cluster bootstrap selected. Notifications off, unrelated tabs closed. Backup: screenshots of the four pages in a folder (failure recovery only).

## The path

| Time | Action | Say (paraphrase) |
|---|---|---|
| 0:00 | **The answer**, point at the title and the synthetic-sample banner | "The question from my first slide is at the top. The banner reminds us these numbers come from the synthetic sample, so this demonstrates the method." |
| 0:10 | Point at the first and second KPI, then **Bottom line** | "Each 1 SD of exposure goes with about 2.6% lower employment, interval about -3.9% to -1.6%, beyond the practical bar. Wages: no meaningful change. H1 supported in this sample, H2 no change, which is exactly what was planted." |
| 0:25 | Sidebar: switch **Uncertainty method** to CR1, pause, switch back | "With 19 clusters the method matters. The interval narrows under CR1, but the conclusion does not change." |
| 0:35 | Scroll to the event study | "The pre-period coefficient is near zero, and the gap grows through 2024-2025, consistent with how OEWS pools surveys." |
| 0:45 | **Is it robust?** -> Remove one occupation -> *13-2051 Financial and Investment Analysts* | "Dropping financial analysts barely moves the estimate. No single industry or occupation drives the result, and the placebo is near zero." |
| 0:60 | **Data & limitations**, point at limitations 1-3 | "And this is what the evidence does not show: it is an association, exposure is potential not adoption, and the committed data are synthetic." |
| 0:75 | Return to slides for Discussion | |

## Likely questions the dashboard answers live

| Question | Where |
|---|---|
| What is one observation? | Data & limitations -> "What one row is" |
| How was the sample built? | Data & limitations -> Sample construction (757 rows read -> 572 model-ready) |
| Why wild bootstrap? | Sidebar help text; The answer -> "How the estimate is built" |
| Could one industry drive it? | Is it robust? -> Leave-one-out |
| Is the code right? | Is it robust? -> known-answer validation (planted effect recovered) |
| Can I reproduce it? | Data & limitations -> Provenance (checksums), docs/A7_CLEAN_RUN.md |
| What about financial analysts specifically? | Occupation explorer -> spot check 13-2051 and analyst vs. clerk (descriptive) |
