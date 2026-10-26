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

**What the AI produced:** a first draft of the `src/oews_eda/` package (data-quality gate, descriptive functions, hypothesis tests with assumption checks, cluster-robust OLS, figure functions, `run_all` runner and CLI), `tests/test_eda.py`, `notebooks/02_eda.ipynb` and its builder script, and first drafts of `docs/EDA_METHODOLOGY.md`, `docs/A5_EXECUTIVE_SUMMARY.md` and `docs/A5_EVIDENCE_MAP.md`. All of it was built on my A3 research design and my A4 database.

**What is mine:** the research question, hypotheses (one-sided employment H1, two-sided wages), unit of analysis, pre/post timing and delayed-post robustness check, the decision to cluster by occupation, and the descriptive-only analyst-vs-clerk contrast, all carried over from A3 and A4. I decided which findings go in the executive summary and how they are framed for stakeholders.

**Verification:** I ran `uv sync`, `uv run oews-pipeline run`, `uv run oews-eda`, and `uv run pytest -q` locally, re-ran the notebook, and reviewed the figures, test results and interpretations. All reported numbers come from the synthetic sample and are labeled as such.

---

_Update this file as AI assistance is used in future assignments - add a
new dated entry rather than overwriting prior entries._