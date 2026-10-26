# A5 Rubric Evidence Map

| Criterion (pts) | Requirement | Where to look |
|---|---|---|
| **Statistical Analysis (30)** | Univariate | Notebook §2; `describe.univariate_summary`, `occupation_table`; `reports/eda/univariate_panel.csv`; Figs 2-3 |
| | Bivariate | Notebook §3; `describe.cell_changes`, `group_comparison`, `correlation_with_pvalues`, `trend_index`, `inference.event_time_gaps`; Figs 4, 5, 11 |
| | Multivariate | Notebook §4; `describe.correlation_table`, `inference.ols_cluster` (industry FE, occupation-clustered SEs), `inference.vif`; Figs 6-7; `reports/eda/model_*.csv` |
| | Hypothesis test: hypotheses stated | Notebook §5.1 and §5.2 (H₀/H₁, α, unit, outcome); `GroupTestResult.h0/h1` |
| | Assumptions checked | `inference.check_assumptions` (Shapiro-Wilk, Levene) + Q-Q plots in Fig 8; independence handled by cluster bootstrap, permutation test and clustered SEs |
| | Results interpreted | Interpretation cells after §5.1-5.4; `GroupTestResult.interpretation`; practical-significance verdicts; robustness set and placebo in `reports/eda/hypothesis_tests.csv` |
| **Data Visualization (25)** | Labeled axes, titles, legible legends | All 11 figures in `reports/figures/` (incl. merge attrition, event-time gaps); shared style in `plots.set_style` |
| | Chart type matches question | Table "Figures" in `docs/EDA_METHODOLOGY.md` |
| | Grayscale / colorblind-safe | Okabe-Ito palette + markers, dashes and hatching (`plots.GROUP_STYLE`); annotated heatmap |
| **Code Architecture (25)** | Importable module, not only notebook cells | `src/oews_eda/` (5 modules + CLI `uv run oews-eda`) |
| | Docstrings | Every module and public function |
| | Notebook imports the module | `notebooks/02_eda.ipynb` imports `oews_eda`; defines no analysis functions |
| | Tested | `tests/test_eda.py` (11 tests: quality gate, change calculation, within-industry demeaning, test logic, practical verdicts, OLS vs SciPy, permutation, attrition reconciliation, checksum verification, end-to-end outputs) |
| **Business Insights (20)** | Findings as business implications | Notebook §7 table; `docs/A5_EXECUTIVE_SUMMARY.md` |
| | Executive summary for a non-technical stakeholder | `docs/A5_EXECUTIVE_SUMMARY.md` (bottom line, actions by audience, confidence) |
| | Connects to the A3 research question | Executive summary "The question"; notebook header; H1 direction and two-sided wage test follow A3 |
| **Integration (spec)** | Uses A4 database and pipeline | `oews_eda.data.load_panel` reads `v_analysis_panel`; `validate_panel` re-checks it; `--source raw` rerun path |
| **Documentation (required)** | Methodology, code docs, insights summary | `docs/EDA_METHODOLOGY.md`, `docs/A5_RESEARCH_DESIGN.md`, docstrings, `docs/A5_EXECUTIVE_SUMMARY.md` |
| **AI disclosure** | `docs/AI_USE.md` current | Assignment 5 entry |

## A4 feedback addressed in A5

| Feedback item | Where it is answered |
|---|---|
| Keep sample vs licensed data explicit | Figure footnotes, `source_mode` in every output, data-status box in the executive summary |
| How a reviewer obtains production inputs and verifies checksums and vintages | `docs/DATA_ACCESS.md` "Full-data verification"; `reports/eda/eda_run_log.json`; `uv run oews-eda --verify-against` |
| Supervised run / run log with checksums / access controls | Same section (three options) |
| Identical source rows vs duplicate transactions | `docs/QUALITY_REPORT.md` §4 (regenerated wording), `docs/DATA_DICTIONARY.md`, `data.validate_panel` docstring |
| What is one row; source of each field | `docs/A5_RESEARCH_DESIGN.md` §1; `reports/eda/panel_definition.csv` |
| Crosswalks that make each join valid | §2; `reports/eda/crosswalks.csv` |
| Cells surviving each merge and filter | §3; Fig 10; `reports/eda/attrition.csv` |
| Exposure = potential, not adoption; differential association | §5; figure titles; test interpretations; executive summary |
| Comparison group and event timing | §4-5; within-industry primary test; Fig 11 |
| Causal assumptions | §5 (six listed) |
| OEWS methodology break, pooling, NAICS change | §4; `data.OEWS_VINTAGE`; excluding-2021 robustness test |
| Enough post-period to separate from broader shocks? | §4 (last bullet) |
| Employment and wages distinct | §1; separate tests, models and figures |
| Practically meaningful estimate under uncertainty | §6; `inference.practical_significance` |
| Conclusions unsupported by the fields | §7; executive summary "What these data cannot tell you" |
