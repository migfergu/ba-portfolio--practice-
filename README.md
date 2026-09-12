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
├── src/                # Reusable Python modules (functions, classes, pipelines)
├── tests/              # Unit tests (pytest)
├── docs/               # Project documentation, including AI_USE.md
├── data/
│   ├── raw/            # Original, unmodified source data (gitignored contents)
│   └── processed/      # Cleaned/derived data (gitignored contents)
├── notebooks/          # Jupyter notebooks for exploration and analysis
├── pyproject.toml      # Project metadata and dependencies (UV-managed)
├── .gitignore
├── LICENSE
└── README.md
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

Miguel L. Ferguson II — PhD student, Business Analytics, University of South
Alabama; finance and business analytics professional.
