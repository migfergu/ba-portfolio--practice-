# Business Analytics Portfolio

Portfolio repository for business analytics coursework, built around financial
modeling, forecasting, budgeting/variance analysis, and data-driven decision
support. This repo is the environment and structural foundation for all
subsequent assignments in the course, and will grow into a final portfolio
project.

## Project Description

This repository demonstrates:
- Professional Python environment management using **UV**
- Reproducible, version-controlled project organization
- A folder structure suited to business analytics workflows (data ingestion,
  source code, notebooks for exploration, tests, and documentation)

## Repository Structure

```
business-analytics-portfolio/
â”œâ”€â”€ src/                # Reusable Python modules (functions, classes, pipelines)
â”œâ”€â”€ tests/              # Unit tests (pytest)
â”œâ”€â”€ docs/               # Project documentation, including docs/AI_USE.md
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ raw/            # Original, unmodified source data (gitignored contents)
â”‚   â””â”€â”€ processed/      # Cleaned/derived data (gitignored contents)
â”œâ”€â”€ notebooks/          # Jupyter notebooks for exploration and analysis
â”œâ”€â”€ pyproject.toml      # Project metadata and dependencies (UV-managed)
â”œâ”€â”€ .gitignore
â”œâ”€â”€ LICENSE
â””â”€â”€ README.md
```

## Environment Setup (UV)

This project uses [UV](https://docs.astral.sh/uv/) to manage the Python
version, virtual environment, and dependencies.

### 1. Install UV

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify installation:
```bash
uv --version
```

### 2. Clone the repository

```bash
git clone https://github.com/<your-username>/business-analytics-portfolio.git
cd business-analytics-portfolio
```

### 3. Create the environment and install dependencies

UV reads `pyproject.toml` and creates a `.venv` automatically:

```bash
uv sync
```

This installs Python 3.10+ (downloading it if needed) and all dependencies
listed in `pyproject.toml` (`pandas`, `numpy`, `jupyter`).

### 4. Add additional dependencies as needed

```bash
uv add pandas numpy jupyter
```

Development-only tools (testing, linting) are grouped under the `dev` extra:

```bash
uv sync --extra dev
```

### 5. Run commands inside the environment

```bash
uv run python src/example.py
uv run jupyter notebook
uv run pytest
```

`uv run` executes a command inside the project's managed virtual environment
without requiring manual activation.

## Common UV Commands Reference

| Command | Purpose |
|---|---|
| `uv --version` | Confirm UV is installed |
| `uv sync` | Create/update the venv to match `pyproject.toml` |
| `uv add <package>` | Add a new dependency |
| `uv remove <package>` | Remove a dependency |
| `uv run <command>` | Run a command inside the project environment |
| `uv lock` | Regenerate the lockfile |
| `uv venv` | Manually create a virtual environment |

## Git Workflow

Standard workflow for this repository:

```bash
git add <files>
git commit -m "Descriptive message"
git push origin main
```

Commit message convention used in this repo: short, imperative summary of
what changed (e.g., "Add initial project structure", "Configure UV
environment", "Add documentation").

## AI Use Disclosure

Per course policy, `docs/AI_USE.md` documents where and how AI tools were
used in this repository. It is kept current as the project evolves.

## Author

Miguel L. Ferguson II â€” PhD student, Business Analytics, University of South
Alabama; finance and business analytics professional.
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
uv run pytest -q                  # 8 tests
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
uv run pytest -q           # 22 tests (11 A4 + 11 A5)
uv run oews-eda --verify-against reports/eda/eda_run_log.json   # input SHA-256 check
```

- [Executive summary](docs/A5_EXECUTIVE_SUMMARY.md) (non-technical)
- [Analysis notebook](notebooks/02_eda.ipynb) (imports `oews_eda`)
- [Methodology and code documentation](docs/EDA_METHODOLOGY.md)
- [Research-design notes answering the A4 feedback](docs/A5_RESEARCH_DESIGN.md)
- [Rubric evidence map](docs/A5_EVIDENCE_MAP.md)
