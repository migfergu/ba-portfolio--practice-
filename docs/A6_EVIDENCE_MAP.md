# A6 Rubric Evidence Map

Pathway 2 (research-oriented). All results are from the synthetic sample.

| Criterion (pts) | Requirement | Where to look |
|---|---|---|
| **Method Implementation (30)** | Method justified against question, design, unit, data type | `docs/A6_METHOD.md` §1 ("Why this method fits"); notebook §2 |
| | Variable construction documented | `docs/A6_METHOD.md` §2; `analysis.model_frame` docstring |
| | Reproducible code and results | `uv run oews-model` regenerates every table and figure; `model_run_log.json` (input/output SHA-256s); `--verify-against` |
| | Seeds set where randomness is used | bootstrap weights, permutations and generator seeds all take explicit seeds (default 751) |
| **Evaluation & Validation (25)** | Estimand, unit, specification, uncertainty method | `docs/A6_METHOD.md` §1, §4 |
| | Appropriate uncertainty | CR1, wild cluster restricted bootstrap, randomization inference; Monte Carlo calibration showing CR1 over-rejects and WCR/RI hold size (`docs/A6_EVALUATION_REPORT.md` §2) |
| | Diagnostics | pre-period coefficient, placebo, leave-one-out, FE-vs-dummy equivalence (`docs/A6_EVALUATION_REPORT.md` §4) |
| | **Comparison specification** | pooled OLS and cell + year FE vs the A3 model, plus the A5 descriptive gap (`docs/A6_EVALUATION_REPORT.md` §3; fig13) |
| | Robustness / sensitivity | delayed post (two ways), panel-share dose, balanced cells, excluding May 2021, Job Zone × post, placebo, leave-one-out (§5; fig13-14) |
| | Validation against a known answer | noise-free recovery vs oracle and closed form, pinned tolerances, mutation tests, 200-seed bands (§1; `tests/test_known_answer.py`, `tests/test_model.py`) |
| **Business or Research Relevance (25)** | Answers the A3 question at the level the design supports | `docs/A6_INTERPRETATION.md` §1-2 |
| | Estimand, substantive magnitude, inferential boundary | `docs/A6_INTERPRETATION.md` §1-2 (per-SD and interquartile magnitude, association not effect) |
| | Limitations named honestly | `docs/A6_INTERPRETATION.md` §6; synthetic-data framing throughout |
| **Technical Excellence (20)** | Importable module with clear estimate/report interface | `src/oews_model/` (`estimate.fit`, `analysis.run_spec`, `report.run_all`); interface table in `docs/A6_METHOD.md` §7 |
| | Error handling and documented execution | `ModelError` (too few clusters, no variation, no rows); quality gate before estimation; CLI exit codes; tests for both |
| | Reusable result artifacts | `reports/model/*.csv`, `model_summary.json`, fig12-14 for the A7 dashboard |
| | Integrates with A4 and A5 modules | reads the A4 SQLite database via `oews_eda.data.load_panel` and `validate_panel`; reuses `OEWS_VINTAGE`, the run-log and verification code |
| | Tested | 42 tests (`uv run pytest -q`), 20 of them new for A6 and the known-answer checks |

## A5 feedback, item by item

| A5 feedback | Response | Evidence |
|---|---|---|
| 1. Quantify the known-answer test | Closed-form slope (−1.20 pts per +0.1) and β (−0.0309) derived; oracle and tolerances defined; tests fail on drift | `oews_eda/known_answer.py`, `oews_model/validation.py`, both test files, Evaluation §1 |
| 2. Keep real-world mechanisms out of synthetic results | A5 executive summary, research design §4 and notebook reworded; pooling statements moved to "what this will say on real data" | `docs/A5_EXECUTIVE_SUMMARY.md`, `docs/A5_RESEARCH_DESIGN.md`, `notebooks/02_eda.ipynb`, `docs/A6_INTERPRETATION.md` §3 |
| 3. Find the missing year | Each candidate traced; noise-free run recovers the 2023 effect exactly; seed 751's 2023 value is a 1-in-200 draw, not a defect; mutation test shows the check would catch a real one-year shift | Evaluation §1.3 |
| 4. Small items | fig11 label/title overlap fixed (and title made neutral); README test count corrected; duplicate dev dependencies removed | `src/oews_eda/plots.py`, `README.md`, `pyproject.toml` |
