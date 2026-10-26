# A5 Rubric Evidence Map

| Criterion (pts) | Requirement | Where to look |
|---|---|---|
| **Statistical Analysis (30)** | Univariate | Notebook §2; `describe.univariate_summary`, `occupation_table`; `reports/eda/univariate_panel.csv`; Figs 2-3 |
| | Bivariate | Notebook §3; `describe.cell_changes`, `group_comparison`, `correlation_with_pvalues`, `trend_index`; Figs 4-5 |
| | Multivariate | Notebook §4; `describe.correlation_table`, `inference.ols_cluster` (industry FE, occupation-clustered SEs), `inference.vif`; Figs 6-7; `reports/eda/model_*.csv` |
| | Hypothesis test: hypotheses stated | Notebook §5.1 and §5.2 (H₀/H₁, α, unit, outcome); `GroupTestResult.h0/h1` |
| | Assumptions checked | `inference.check_assumptions` (Shapiro-Wilk, Levene) + Q-Q plots in Fig 8; independence handled by cluster bootstrap, permutation test and clustered SEs |
| | Results interpreted | Interpretation cells after §5.1 and §5.2; `GroupTestResult.interpretation`; delayed-post robustness |
| **Data Visualization (25)** | Labeled axes, titles, legible legends | All 9 figures in `reports/figures/`; shared style in `plots.set_style` |
| | Chart type matches question | Table "Figures" in `docs/EDA_METHODOLOGY.md` |
| | Grayscale / colorblind-safe | Okabe-Ito palette + markers, dashes and hatching (`plots.GROUP_STYLE`); annotated heatmap |
| **Code Architecture (25)** | Importable module, not only notebook cells | `src/oews_eda/` (5 modules + CLI `uv run oews-eda`) |
| | Docstrings | Every module and public function |
| | Notebook imports the module | `notebooks/02_eda.ipynb` imports `oews_eda`; defines no analysis functions |
| | Tested | `tests/test_eda.py` (7 tests: quality gate, change calculation, test logic, OLS vs SciPy, permutation, end-to-end outputs) |
| **Business Insights (20)** | Findings as business implications | Notebook §7 table; `docs/A5_EXECUTIVE_SUMMARY.md` |
| | Executive summary for a non-technical stakeholder | `docs/A5_EXECUTIVE_SUMMARY.md` (bottom line, actions by audience, confidence) |
| | Connects to the A3 research question | Executive summary "The question"; notebook header; H1 direction and two-sided wage test follow A3 |
| **Integration (spec)** | Uses A4 database and pipeline | `oews_eda.data.load_panel` reads `v_analysis_panel`; `validate_panel` re-checks it; `--source raw` rerun path |
| **Documentation (required)** | Methodology, code docs, insights summary | `docs/EDA_METHODOLOGY.md`, docstrings, `docs/A5_EXECUTIVE_SUMMARY.md` |
| **AI disclosure** | `docs/AI_USE.md` current | Assignment 5 entry |
