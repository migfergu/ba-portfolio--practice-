# AI Use Disclosure

This document discloses how AI tools were used in the development of this
repository, per the course AI policy.

## Assignment 2: Environment Setup & Repository Creation

**AI Tool(s) Used:** Claude (Anthropic)

**Scope of Use:**
- Generated the initial folder structure (`src/`, `tests/`, `docs/`,
  `data/`, `notebooks/`) following course standards.
- Drafted `pyproject.toml`, `.gitignore`, `LICENSE`, and `README.md`
  boilerplate content.
- Drafted this `AI_USE.md` template.

**Work Completed Independently:**
- Reviewed and verified all generated files for accuracy before committing.
- Installed and configured UV locally; ran `uv sync` and `uv add` commands
  myself and confirmed the environment worked (`uv --version`,
  dependency installation).
- Performed all Git operations (`git init`, `git add`, `git commit`,
  `git push`) myself.
- Will author actual analysis code, notebooks, and tests in subsequent
  assignments without AI-generated content unless separately disclosed here.

**Verification:**
I reviewed all AI-assisted content for correctness and adjusted it to match
my own project conventions before submitting.

## Assignment 3: Project Proposal & Data Source Identification

**Files:** `docs/BUS_751_Assignment3_ProjectProposal.pdf` (Markdown copy: `docs/BUS_751_Assignment3_ProjectProposal.md`)
**Tool:** Claude (Anthropic)
**Date:** September 2026

**Author's contribution.** The research ideas and the direction of this study are my own. The proposal builds on a combination of my previous work on generative AI and financial analysts. I wrote and revised the submitted text, made the final design choices, and am responsible for its content and citations.

**How AI was used.**
- Formatting the proposal and cleaning up its presentation
- Earlier in the process, discussing and drafting alternative versions of the proposal's structure, research design, and data sources, which I used as reference while developing my own version
- Converting the final Word document to PDF and Markdown for this repository

## Assignment 4: Database Design & Data Pipeline

**Tool:** Claude (Anthropic), October 2026.

**What the AI produced:** a first draft of the Python package under `src/oews_pipeline/` (extract, transform, validation, load, quality report, re-run check, CLI), the synthetic-sample generator, the pytest suite, and first drafts of `docs/ERD.md`, `docs/DATA_DICTIONARY.md`, `docs/DATA_ACCESS.md`, and `docs/PIPELINE.md`. These were built from the research design in my A3 proposal.

**What is mine:** the research question, unit of analysis, data sources, exposure definition, pre/post timing, focal-occupation contrast, and robustness plan, all carried over from A3. I chose the schema grain and approved the rules for handling bad records. I reviewed each module, ran the pipeline, re-run check, and tests locally, and checked the quality report.

**Verification:** I ran `uv run oews-pipeline run`, `uv run oews-pipeline rerun-check`, and `uv run pytest -q` locally and reviewed the generated `QUALITY_REPORT.md` and `RERUN_CHECK.md`.

## Assignment 5: Exploratory Data Analysis Module

**Tool:** Claude (Anthropic), October 2026.

**What the AI produced:** a first draft of the `src/oews_eda/` package (data-quality gate, descriptive functions, hypothesis tests with assumption checks, cluster-robust OLS, figure functions, `run_all` runner and CLI), `tests/test_eda.py`, `notebooks/02_eda.ipynb` and its builder script, and first drafts of `docs/EDA_METHODOLOGY.md`, `docs/A5_RESEARCH_DESIGN.md`, `docs/A5_EXECUTIVE_SUMMARY.md`, `docs/A5_EVIDENCE_MAP.md` and the full-data verification section of `docs/DATA_ACCESS.md`. It also looked up the OEWS technical notes (pooled panels, MB3, SOC/NAICS versions) used in the design notes, and reworded the duplicate-row text in the A4 quality report in response to the A4 feedback. All of it was built on my A3 research design and my A4 database.

**What is mine:** the research question, hypotheses (one-sided employment H1, two-sided wages), unit of analysis, pre/post timing and delayed-post robustness check, the decision to cluster by occupation, and the descriptive-only analyst-vs-clerk contrast, all carried over from A3 and A4. I decided which findings go in the executive summary and how they are framed for stakeholders, and directed the changes made in response to the A4 feedback (within-industry comparison group, event timing, practical-significance threshold, verification path).

**Verification:** I ran `uv sync`, `uv run oews-pipeline run`, `uv run oews-eda`, `uv run oews-eda --verify-against reports/eda/eda_run_log.json`, and `uv run pytest -q` locally, re-ran the notebook, and reviewed the figures, test results and interpretations. All reported numbers come from the synthetic sample and are labeled as such.

## Assignment 6: Analytics Engine & Modeling

**Tool:** Claude (Anthropic), October 2026.

**What the AI produced:** a first draft of the `src/oews_model/` package (fixed-effect absorption and CR1 inference, wild cluster restricted bootstrap, randomization inference, specification suite, event study, leave-one-out, finance contrast, Monte Carlo validation, figures, `run_all` runner and CLI), `src/oews_eda/known_answer.py`, the noise and effect-size parameters added to the synthetic generator, `tests/test_model.py` and `tests/test_known_answer.py` (including the mutation tests), `notebooks/03_model.ipynb` and its builder, and first drafts of `docs/A6_METHOD.md`, `docs/A6_EVALUATION_REPORT.md`, `docs/A6_INTERPRETATION.md` and `docs/A6_EVIDENCE_MAP.md`. In response to the A5 feedback it also traced the 2023 event-time result (noise-free runs and a 200-seed distribution), reworded the A5 executive summary, research-design notes and notebook so that synthetic results are not attributed to OEWS pooling, fixed the fig11 label overlap and the README test count, and removed the duplicated dev dependencies.

**What is mine:** the research question, estimand, unit of analysis, fixed-effect specification, occupation clustering, hypotheses (one-sided employment, two-sided wages), delayed-post and event-time robustness plan, and the descriptive-only analyst-vs-clerk contrast, all carried over from A3-A5, and the decision to address every A5 feedback item before building A6. _[Ferg: add the choices you made or changed while reviewing this draft.]_

**Verification:** _[Ferg: list what you ran locally, e.g. `uv sync --extra dev`, `uv run oews-pipeline run`, `uv run oews-eda`, `uv run oews-model`, `uv run oews-model simulate`, `uv run pytest -q`, the notebook, and the outputs you reviewed.]_ All reported numbers come from the synthetic sample and are labeled as such.

---

_Update this file as AI assistance is used in future assignments - add a
new dated entry rather than overwriting prior entries._