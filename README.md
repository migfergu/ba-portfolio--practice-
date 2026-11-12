# Generative AI Exposure and Financial Analyst Employment and Wages

BUS 751 (Python for Business Analytics) portfolio project, University of South Alabama. Research pathway.

**Question.** After ChatGPT's release in late 2022, did U.S. occupations whose tasks are more exposed to generative AI see different employment and wage changes than less-exposed occupations in the same industry? The unit is occupation x 4-digit industry x May reference year (BLS OEWS), exposure comes from Eloundou et al. (2024), and the estimate is a fixed-effects difference-in-differences with occupation-clustered, small-cluster inference. Results are framed as associations, not proof of displacement.

> **Data.** The repository runs end to end on a committed **synthetic sample** with a planted employment effect and no wage effect, so every result is reproducible without licensed data. Real BLS, Eloundou and O*NET files are never committed; see [docs/DATA_ACCESS.md](docs/DATA_ACCESS.md).

## Quick start: the dashboard (Assignment 7)

Requires [uv](https://docs.astral.sh/uv/) and Git. Install uv with `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` (Windows) or `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux); uv installs Python itself.

```powershell
git clone https://github.com/migfergu/migfergu-ba-portfolio-practice.git
cd migfergu-ba-portfolio-practice
uv sync --locked --extra dev          # exact environment from uv.lock
uv run oews-pipeline run              # build the A4 database from the synthetic sample (~5 s)
uv run streamlit run streamlit_app.py # open http://localhost:8501
```

Verify: `uv run pytest -q` (includes Streamlit smoke tests of every page) and `uv run oews-dashboard-check` (writes the dated clean-run record [docs/A7_CLEAN_RUN.md](docs/A7_CLEAN_RUN.md)).

## Repository layout

```
streamlit_app.py          A7 dashboard entrypoint (navigation + shared sidebar)
app_pages/                A7 dashboard pages (layout only; no estimation)
src/oews_pipeline/        A4 ETL: extract, validate, transform, load -> data/processed/oews_genai.db
src/oews_eda/             A5 EDA: loader, quality gate, descriptives, tests, figures
src/oews_model/           A6 analytics engine: fixed effects, small-cluster inference, robustness, validation
src/oews_dashboard/       A7 data-access layer, shared UI helpers, clean-run check
tests/                    pytest suite for A4-A7
notebooks/                analysis notebooks that import the packages above
reports/                  committed figures and result tables (synthetic sample)
data/sample/              synthetic sample inputs (raw/ and processed/ contents are git-ignored)
docs/                     method, evaluation, data access, evidence maps, AI use disclosure
config/sources.toml       source files, years and pre/post timing
pyproject.toml, uv.lock   pinned environment (uv)
.github/workflows/        CI: clean-clone install, pipeline, tests, dashboard check
```

## Assignment 7: Dashboard & Release Readiness

A four-page Streamlit dashboard for workforce-planning leaders in finance and a research committee. It answers the question on the first screen (four KPIs, a plain-language bottom line with hypothesis verdicts, and what the evidence does not show), then lets the user check robustness (specification suite, placebo, leave-one-out, known-answer validation), explore occupations and industries (A5 descriptives with filters), and inspect data provenance and limitations.

* Reads the A4 database through the A5 loader, reuses A5 descriptive and plotting functions, and reads the saved A6 artifacts in `reports/model/`. Pages never re-estimate the model (enforced by a test).
* Verifies provenance on every page: database input checksums vs. the model run log, and result-file checksums vs. the values recorded at run time.
* Handles a missing database (one-click sample build), missing or edited results, and empty filters with messages that name the fix.

Docs: [user guide](docs/APP_GUIDE.md) - [presentation demo path](docs/A7_DEMO_SCRIPT.md) - [clean-run record](docs/A7_CLEAN_RUN.md) - [rubric evidence map](docs/A7_EVIDENCE_MAP.md)

## Assignment 4: Database & Data Pipeline

Builds a SQLite database for **Generative AI Exposure and Financial Analyst Employment and Wages** from BLS OEWS, Eloundou et al. (2024) exposure scores, and O*NET Job Zones.

### Setup (about 2 minutes)

Requires [uv](https://docs.astral.sh/uv/) and Git. Python is installed by uv automatically.

```powershell
git clone https://github.com/migfergu/migfergu-ba-portfolio-practice.git
cd migfergu-ba-portfolio-practice
uv sync                           # install dependencies from uv.lock
uv run oews-pipeline run          # build data/processed/oews_genai.db from the synthetic sample
uv run oews-pipeline rerun-check  # run twice, prove no duplicates -> docs/RERUN_CHECK.md
uv run pytest -q                  # full test suite (A4-A7)
```

Using the real data instead of the sample: see [docs/DATA_ACCESS.md](docs/DATA_ACCESS.md), then run `uv run oews-pipeline run --source raw`.

### Documentation

- [Pipeline architecture & commands](docs/PIPELINE.md)
- [ERD & indexing strategy](docs/ERD.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Quality report](docs/QUALITY_REPORT.md) and [re-runnability check](docs/RERUN_CHECK.md)
- [Rubric evidence map](docs/A4_EVIDENCE_MAP.md)

## Assignment 5: Exploratory Data Analysis

Reusable EDA package `src/oews_eda/` on top of the A4 database: row definition and merge attrition, data-quality gate, univariate/bivariate/multivariate analysis, within-industry hypothesis tests with assumption checks and practical-significance verdicts, event-time gaps that account for OEWS panel pooling, a pre-period placebo, occupation-clustered regression, eleven colorblind-safe figures, and a checksum run log for full-data verification.

> Committed results are from the **synthetic sample**. Licensed source files are never committed; see [Full-data verification](docs/DATA_ACCESS.md#full-data-verification-privacy--and-license-compliant).

```powershell
uv sync
uv run oews-pipeline run   # build the database (sample; --source raw for real data)
uv run oews-eda            # regenerate reports/figures/*.png and reports/eda/*
uv run pytest -q           # full test suite (A4-A7)
uv run oews-eda --verify-against reports/eda/eda_run_log.json   # input SHA-256 check
```

- [Executive summary](docs/A5_EXECUTIVE_SUMMARY.md) (non-technical)
- [Analysis notebook](notebooks/02_eda.ipynb) (imports `oews_eda`)
- [Methodology and code documentation](docs/EDA_METHODOLOGY.md)
- [Research-design notes answering the A4 feedback](docs/A5_RESEARCH_DESIGN.md)
- [Rubric evidence map](docs/A5_EVIDENCE_MAP.md)

## Assignment 6: Analytics Engine & Modeling

Importable package `src/oews_model/` that estimates the A3 specification, log Y = cell FE + industry-by-year FE + β·(exposure × post), on the A4 database through the A5 loader. It reports CR1, wild-cluster-bootstrap and randomization inference for 19 occupation clusters; compares the model with pooled OLS and cell + year FE; and runs an event study (2022 = 0), timing, sample, placebo and leave-one-out checks, the wage outcome, and the descriptive analyst/clerk contrast. It also validates the code against the synthetic generator's known answer (noise-free recovery with pinned tolerances, mutation tests, 200-seed sampling bands) and calibrates the inference by Monte Carlo.

> Committed results are from the **synthetic sample** (planted employment effect, no wage effect, no OEWS pooling). They test the method, not the labor market.

```powershell
uv sync --extra dev
uv run oews-pipeline run                 # A4 database
uv run oews-model                        # estimates, robustness, validation, fig12-14 (~3-4 min)
uv run oews-model simulate               # Monte Carlo calibration tables (~5 min)
uv run pytest -q                         # full test suite (A4-A7)
uv run oews-model --verify-against reports/model/model_run_log.json
```

- [Method](docs/A6_METHOD.md) (estimand, unit, specification, uncertainty, interface)
- [Evaluation report](docs/A6_EVALUATION_REPORT.md) (known-answer validation, Monte Carlo, comparison, diagnostics, robustness)
- [Research interpretation](docs/A6_INTERPRETATION.md) (magnitude, inferential boundary, limitations)
- [Analysis notebook](notebooks/03_model.ipynb) (imports `oews_model`)
- [Rubric evidence map](docs/A6_EVIDENCE_MAP.md)
- Result artifacts read by the A7 dashboard: `reports/model/`

## AI use disclosure

Per course policy, [docs/AI_USE.md](docs/AI_USE.md) documents where and how AI tools were used, one dated entry per assignment.

## Author

Miguel L. Ferguson II - PhD student, Business Analytics, University of South Alabama.
