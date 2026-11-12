# Dashboard user guide (Assignment 7)

**Generative AI Exposure and Financial Analyst Employment and Wages** - Streamlit dashboard

## Who it is for and what it answers

**Audience.** Workforce-planning and talent leaders in finance organizations, and a research committee reviewing the study. No Python, statistics or OEWS background is assumed.

**The one question it makes clear.** *After ChatGPT's release in late 2022, did occupations whose tasks are more exposed to generative AI see different employment and wage changes than less-exposed occupations in the same industry?*

**Decision it supports.** Whether GenAI task exposure should be treated as an early-warning signal for slower employment growth when planning finance-sector roles, and how much confidence the evidence deserves. It is a planning signal, not a forecast for any single job or worker.

**Ninety-second read.** The first screen shows the question, four KPIs (employment gap, wage gap, pre-trend check, sample size), a plain-language bottom line with the hypothesis verdicts, and what the evidence does not show.

## Setup and launch (clean clone, about 3 minutes)

Requires [uv](https://docs.astral.sh/uv/) and Git. uv installs the pinned Python packages from `uv.lock`.

```powershell
git clone https://github.com/migfergu/migfergu-ba-portfolio-practice.git
cd migfergu-ba-portfolio-practice
uv sync --locked --extra dev        # exact environment from uv.lock (includes streamlit)
uv run oews-pipeline run            # build the A4 database from the committed synthetic sample (~5 s)
uv run streamlit run streamlit_app.py
```

The app opens at <http://localhost:8501>. Port busy: add `--server.port 8502`.

The saved Assignment 6 results in `reports/model/` are committed, so the dashboard does **not** need `uv run oews-model` (3-4 minutes) to start. If you skip the pipeline step, the results pages still load, and the explorer and data pages offer a **Build the sample database now** button.

**Verify the install:**

```powershell
uv run pytest -q                    # full suite, including Streamlit AppTest smoke tests of every page
uv run oews-dashboard-check         # dated clean-run record -> docs/A7_CLEAN_RUN.md
```

**Secrets.** The app needs no credentials, API keys or network access. `.streamlit/config.toml` holds only display settings; `.streamlit/secrets.toml` and `.env` are git-ignored.

## Pages and interactions

The sidebar holds two controls that apply to every page:

| Control | Options | Why it matters |
|---|---|---|
| Outcome | Employment (default), Wages | Employment tests H1 (one-sided, beta < 0); wages are two-sided |
| Uncertainty method | Wild cluster bootstrap (default), CR1 cluster-robust t | With 19 occupation clusters, the bootstrap is the more reliable interval |

| Page | What it shows | Interaction |
|---|---|---|
| **The answer** | Question, 4 KPIs, bottom line with H1/H2 verdicts, planning translation (25th to 75th percentile exposure), what it does not show, event-study figure and table | Outcome and uncertainty method change the interval, verdict and timing view |
| **Is it robust?** | 4 KPIs (main estimate, alternatives with same sign, alternatives clearing the practical bar, placebo), specification forest and table, leave-one-out, known-answer validation | Choose to remove one industry or one occupation and see the estimate without it |
| **Occupation explorer** | Descriptive evidence from the database: trend index by exposure tercile, exposure vs. within-industry change by occupation, a per-occupation spot check, analyst vs. clerk contrast | Sidebar filters: industries, exposure terciles, balanced-cells toggle; occupation picker |
| **Data & limitations** | Eight limitations, provenance with SHA-256 verification, sample-construction attrition, A5 quality gate, row definition, OEWS release facts, recovery steps | None needed; reference page |

**Recommended demo path (one user decision).** The answer (read the employment KPI and bottom line) -> switch Uncertainty method to CR1 and back to show the conclusion does not depend on it -> Is it robust? (remove *Financial and Investment Analysts* to show no single occupation drives the result) -> Occupation explorer (filter to finance industries 5221, 5231, 5239, 5241; spot-check 13-2051) -> Data & limitations (point to limitations 1-4). See `docs/A7_DEMO_SCRIPT.md`.

## How to interpret the numbers

* **"Gap per 1 SD more exposure"** is the A3 model coefficient beta converted to percent: (exp(beta) - 1) x 100. One SD of exposure is about 26 percentage points of an occupation's tasks. A value of -2.6% means: for each 1 SD more exposure, employment after 2022 was about 2.6% lower relative to less-exposed occupations in the same industry and to the occupation-industry cell's own pre-2023 level.
* **Practical bar.** A result is "practically meaningful" only when its whole 95% interval is beyond +/-1 log point per SD; "negligible" when the whole interval is inside it; otherwise "inconclusive" or "nonzero but may be below the bar". The rule is `oews_model.analysis.practical_verdict` (A6).
* **Pre-trend check.** The 2021 event-study coefficient. An interval that includes zero supports the assumption that high- and low-exposure occupations moved together before ChatGPT.
* **Event study.** Each May OEWS estimate pools six semiannual survey panels over three years, so May 2023 contains one post-ChatGPT panel and May 2025 five. A gap that grows through 2024-2025 is what that pooling would produce.
* **Explorer charts are descriptive.** The trend index (geometric mean, 2022 = 100) and occupation changes come from A5 functions and do not include industry-by-year controls or formal uncertainty. They show where the model estimate comes from; they do not replace it.

## Data assumptions

| Assumption | Detail |
|---|---|
| Unit of analysis | Detailed occupation x 4-digit NAICS industry x May reference year (BLS OEWS national industry-specific) |
| Period | May 2021-2022 pre, May 2023-2025 post (delayed-post robustness: 2024+) |
| Exposure | Eloundou et al. (2024) share of tasks exposed (E1 + E2), fixed, standardized across occupations |
| Committed data | **Synthetic sample** in `data/sample/` with a planted employment effect and no wage effect. Every page shows a banner saying so |
| Real data | Licensed or large source files stay outside Git. Build with `uv run oews-pipeline run --source raw`, then `uv run oews-model`; the dashboard switches its labels to the real-data run automatically. See `docs/DATA_ACCESS.md` |
| Suppression | OEWS-suppressed values are kept missing with a flag, never imputed |

## Architecture (where each number comes from)

```
streamlit_app.py                 entrypoint: navigation + shared sidebar controls
app_pages/1_answer.py ... 4_*    page layout only; no estimation code (enforced by a test)
src/oews_dashboard/ui.py         cached loaders, sidebar state, provenance banner, empty/error states
src/oews_dashboard/data_access.py  documented data-access layer:
    A4 database  -> oews_eda.data.load_panel / validate_panel / attrition_table / input_manifest
    A5 analysis  -> oews_eda.describe.trend_index / cell_changes / occupation_changes / focal_contrast
    A6 results   -> reads reports/model/*.csv + model_summary.json + model_run_log.json
    A6 figures   -> oews_model.plots.plot_event_study / plot_spec_forest / plot_leave_one_out
src/oews_dashboard/verify.py     clean-run check -> docs/A7_CLEAN_RUN.md
tests/test_dashboard.py          data-layer tests + AppTest smoke tests of every page and failure state
```

**Provenance check.** On every page the app compares the SHA-256 of the input files recorded in `reports/model/model_run_log.json` with the inputs of the database you built, and the SHA-256 of each result file with the value recorded when the model ran. A mismatch is shown as an error with the command that fixes it.

**Caching.** Loaders use `st.cache_data`, keyed on file modification times, so filters respond instantly and rebuilding the database or re-running the model refreshes the app without a restart.

**Overrides.** `OEWS_DB_PATH` and `OEWS_MODEL_DIR` environment variables point the app at another database or result folder (used by the tests; useful for a real-data database kept outside the repository).

## Limitations (also on the Data & limitations page)

1. Committed results are from a synthetic sample: they validate the method, not the labor market.
2. Association, not causation: post-2022 shocks that hit high-exposure occupations differently are not separated from GenAI.
3. Exposure measures technical potential, not observed adoption.
4. OEWS pooling dilutes early post-period estimates.
5. Only 19 occupation clusters: small-cluster inference (wild bootstrap, randomization inference) is used.
6. Suppression changes which cells are observed; the balanced-cells check addresses it.
7. Employment is a stock, not hires or separations; mean wages are composition-sensitive.
8. The analyst-vs-clerk contrast is descriptive only.

## Troubleshooting and recovery

| Symptom | Cause | Fix |
|---|---|---|
| Red box "Database not built" | `data/processed/oews_genai.db` missing (it is git-ignored) | `uv run oews-pipeline run`, or click **Build the sample database now** |
| Red box "Model results not found" | `reports/model/` incomplete | `uv run oews-model` (3-4 min) |
| Red box "Results and database disagree" | Database built from different input files than the model run | `uv run oews-model` on the current database |
| Red box "Result files changed" | A file in `reports/model/` was edited by hand | `git checkout reports/model` or `uv run oews-model` |
| `ModuleNotFoundError: streamlit` | Environment not synced | `uv sync --locked --extra dev` |
| `uv sync --locked` says the lockfile is out of date | `pyproject.toml` changed without `uv lock` | `uv lock`, then commit `uv.lock` |
| Yellow box "No industries or exposure groups are selected" | Explorer filters cleared | Re-select in the sidebar |
| Numbers look stale after a rebuild | Browser session cached | App menu -> Clear cache, then Rerun |
| Port 8501 in use | Another app is running | `uv run streamlit run streamlit_app.py --server.port 8502` |
