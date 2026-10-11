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
