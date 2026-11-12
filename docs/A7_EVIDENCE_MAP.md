# Assignment 7 rubric evidence map

Where each requirement of *Assignment 7: Dashboard and Release Readiness* is met. Paths are relative to the repository root.

## Required repository evidence

| Requirement | Evidence |
|---|---|
| One documented launch command | `uv run streamlit run streamlit_app.py` (README Quick start, docs/APP_GUIDE.md) |
| `pyproject.toml` and `uv.lock` current | `streamlit>=1.40,<2` added to dependencies; `uv.lock` regenerated; CI installs with `uv sync --locked` (fails if the lock is stale) |
| Documented data-access layer; no model recalculation in page code | `src/oews_dashboard/data_access.py` (module docstring lists every source); `tests/test_dashboard.py::test_no_model_estimation_in_page_code` fails if a page calls the estimator |
| Missing files, empty results, invalid selections handled | `DataUnavailable` with a fix command; one-click sample build; empty-filter warnings with `st.stop()`; invalid sidebar state falls back to defaults; stale leave-one-out selection guarded. Tested: `test_pages_without_database_show_fix`, `test_pages_without_results_show_fix`, `test_explorer_empty_filter_warns_not_crashes`, `test_empty_selection_returns_empty_frames`, `test_headline_rejects_invalid_choices`, `test_missing_and_corrupt_results_raise_with_fix` |
| No secrets, licensed data or oversized artifacts committed | App needs no credentials; `.streamlit/secrets.toml`, `.env`, `data/raw/*`, `data/processed/*` git-ignored; only the synthetic sample and small result CSVs are tracked |
| README / APP_GUIDE: setup, launch, audience, pages, data assumptions, recovery | `docs/APP_GUIDE.md` (all sections); README Assignment 7 section |
| Smoke test or dated clean-run record | Both: AppTest smoke tests in `tests/test_dashboard.py` (entrypoint + every page x both outcomes + failure states) and `docs/A7_CLEAN_RUN.md` written by `uv run oews-dashboard-check` |
| `docs/AI_USE.md` current | Assignment 7 entry added |

## Rubric criteria

### Dashboard Quality and Communication (35)

* Research question is the page title and first paragraph of **The answer**.
* Hierarchy: question -> 4 KPIs above the fold (employment gap, wage gap, pre-trend check, sample) -> bottom line with H1/H2 verdicts -> planning translation -> timing (event study) -> methods expander -> limitations link. Robustness and explorer pages repeat the KPI -> chart -> detail pattern.
* Interactions tied to a decision: outcome and uncertainty method (does the conclusion depend on the inference choice?), leave-one-out (is one industry or occupation driving it?), explorer filters (which finance industries and occupations sit behind it?).
* Charts: every chart has a descriptive subheader stating what it shows and axis labels with units (percent, log points x100, index 2022 = 100). Line and interval charts reuse the A5/A6 Matplotlib functions, which pair Okabe-Ito colors with markers and line styles so they read in grayscale; the trend view adds an interactive built-in chart and a data tab. At most three series per chart; percent and currency formatting in tables.
* Honesty: synthetic-sample banner on every page, "association, not proof" in every interpretation, practical-significance verdicts, descriptive labels on explorer views, eight limitations on a dedicated page.
* Data freshness: caption on every page with model-run time, commit, database build time and checksum status.

### System and Data Integration (30)

* A4: reads `data/processed/oews_genai.db` through `oews_eda.data` (read-only connection), shows ETL run time, input manifest and attrition.
* A5: reuses `validate_panel`, `attrition_table`, `balanced_cells`, `trend_index`, `cell_changes`, `occupation_changes`, `focal_contrast`, `panel_definition`, `oews_vintage`; nothing is re-implemented.
* A6: reads every saved artifact in `reports/model/` and renders A6's own figure functions (`plot_event_study`, `plot_spec_forest`, `plot_leave_one_out`). No hidden manual steps: the artifacts are committed and their SHA-256 is verified against `model_run_log.json`.
* Graceful states: see "Missing files..." above. Cached loaders keyed on file modification time.

### Reproducibility and Release Readiness (20)

* Clean clone: `uv sync --locked --extra dev` -> `uv run oews-pipeline run` -> `uv run streamlit run streamlit_app.py`.
* Locked dependencies: `uv.lock`; CI enforces `--locked`.
* Verification: `uv run pytest -q`, `uv run oews-dashboard-check` (dated record in `docs/A7_CLEAN_RUN.md`).
* Optional path chosen: GitHub Actions workflow `.github/workflows/dashboard.yml` runs the exact clean-clone steps on a fresh Ubuntu runner on every push. It proves the documented path works from a clean checkout on Linux; it does not deploy the app publicly (no public deployment, because the course forbids publishing licensed data and the real-data run must stay local). Docker was not used.

### Professional Documentation (15)

* `docs/APP_GUIDE.md`: audience, business/research value, setup, launch, pages and interactions, interpretation, data assumptions, architecture, limitations, troubleshooting.
* `docs/A7_DEMO_SCRIPT.md`: the 75-second presentation path and the questions it answers.
* README rewritten with a project summary, Quick start, accurate repository layout and per-assignment sections.
