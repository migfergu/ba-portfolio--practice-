# Data Access and Safe Review Path

## What is and isn't committed

| Committed to git | Never committed (`.gitignore`) |
|---|---|
| Schema DDL (`src/oews_pipeline/schema.py`), ERD, data dictionary | `data/raw/*`: the real OEWS, Eloundou, and O*NET files |
| Synthetic sample in `data/sample/`, plus the generator that rebuilds it byte for byte | `data/processed/*.db`: built databases |
| Source manifest `config/sources.toml` | `logs/` |
| Quality report and re-run check produced **from the sample** | |

The real sources are public, but they are not committed. The OEWS industry-specific workbooks are large binary files that change with each release. O*NET (CC BY 4.0) and the Eloundou et al. file (MIT) carry license terms that are best honored by linking to the source rather than redistributing it. The repository therefore holds a schema, a permitted synthetic sample, and instructions. Anyone reviewing the code can run the whole pipeline without the real data.

## Reviewer path (no real data needed)

```powershell
uv sync
uv run oews-pipeline run            # builds data/processed/oews_genai.db from data/sample/
uv run oews-pipeline rerun-check    # proves idempotency, writes docs/RERUN_CHECK.md
uv run pytest -q
```

## Authorized-user path (real data)

1. **OEWS.** From <https://www.bls.gov/oes/tables.htm>, under *National industry-specific and by ownership*, download `oesm21in4.zip` through `oesm25in4.zip` (May 2021–May 2025). Unzip each one and copy the **4-digit NAICS national** workbook (`nat4d_M{YYYY}_dl.xlsx`) into `data/raw/`.
2. **Exposure.** From <https://github.com/openai/GPTs-are-GPTs>, copy `data/occ_level.csv` into `data/raw/`.
3. **Job Zones.** From the O*NET Resource Center database archive, download **O*NET 27.0** (text format) and copy `Job Zones.txt` into `data/raw/`.
4. Check the file names against `[raw.*]` in `config/sources.toml`. If BLS named a workbook differently inside a zip, change the manifest entry, not the code.
5. Run:
   ```powershell
   uv run oews-pipeline run --source raw
   uv run oews-pipeline rerun-check --source raw
   ```
6. Record the SHA-256 values from `source_file_log` (also shown in `docs/QUALITY_REPORT.md`, section 1) in your lab notes, so later reruns can confirm they used identical inputs.

**Before committing after a raw run:** `QUALITY_REPORT.md` and `RERUN_CHECK.md` will then describe real-data counts. Those are aggregate statistics, not microdata, so they are safe to commit. `data/raw/` and the `.db` file stay ignored either way.

## Header checks the pipeline enforces

Extraction stops with a named error if required columns are missing:
- OEWS: `NAICS, NAICS_TITLE, I_GROUP, OCC_CODE, OCC_TITLE, O_GROUP, TOT_EMP, EMP_PRSE, A_MEAN, MEAN_PRSE` (case-insensitive)
- Exposure: `O*NET-SOC Code, Title`, plus the configured `exposure_measure` column
- Job Zones: `O*NET-SOC Code, Title, Job Zone`

If the Eloundou file uses different rating column names than `dv_rating_alpha/beta/gamma`, set `exposure_measure` in `sources.toml` to the correct header. The pipeline fails fast and names the missing column, rather than loading the wrong measure.

## Full-data verification (privacy- and license-compliant)

Every result in the repository is labeled `SYNTHETIC SAMPLE` or `Real-data run` (figure footnotes, `etl_run.source_mode`, `reports/eda/eda_run_log.json`). Licensed or restricted source files are **never committed**; only aggregate outputs and hashes are. Three ways for a reviewer to verify the full-data workflow without data changing hands through GitHub:

1. **Reproducible run log (default).** After my raw run I commit `reports/eda/eda_run_log.json`, which holds file names, versions, sizes, row counts and SHA-256 hashes for every input, the code commit and library versions. Nothing else is included. An authorized reviewer downloads the same public releases (steps 1-3 above), runs:
   ```powershell
   uv run oews-pipeline run --source raw
   uv run oews-eda --verify-against reports/eda/eda_run_log.json   # exit 0 = byte-identical inputs
   uv run oews-eda                                                  # regenerates every table and figure
   ```
   and compares the regenerated `reports/eda/*.csv` and figures with the committed ones. `--verify-against` prints expected vs found hash and row count per file.
2. **Vintage check.** The run log's `version` fields and `config/sources.toml` name each release: OEWS May 2021-2025 `nat4d` workbooks, Eloundou et al. (2024) `occ_level.csv` from `openai/GPTs-are-GPTs`, and O*NET 27.0. `oews_eda.data.OEWS_VINTAGE` and `docs/A5_RESEARCH_DESIGN.md` §4 record, per release, the pooled panels, MB3 method, SOC and NAICS versions, taken from the BLS technical notes, so a reviewer can confirm the downloaded files are the stated vintages.
3. **Supervised run.** If a reviewer cannot download the files, I can run the raw pipeline live (screen share or in person) from a clean clone, show the hash check passing, and keep the inputs on my machine.

Access controls: `data/raw/` and `data/processed/*.db` are git-ignored; only I hold the raw copies, on my own device. Outputs written by the EDA are aggregates (counts, means, model coefficients) at the published OEWS cell level and contain no microdata.
