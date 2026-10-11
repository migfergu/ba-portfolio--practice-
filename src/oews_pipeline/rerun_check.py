"""Re-runnability check: run the pipeline twice on the same inputs and prove nothing duplicates or drifts."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import DOCS_DIR, PROJECT_ROOT
from .pipeline import run_pipeline
from .schema import connect

log = logging.getLogger(__name__)

ANALYTIC_TABLES = ["dim_occupation", "dim_industry", "dim_year", "occupation_exposure",
                   "occupation_preparation", "fact_oews_estimate"]
AUDIT_TABLES = ["etl_run", "source_file_log", "rejected_record"]   # append one batch per run by design


def fact_fingerprint(db: Path) -> str:
    """SHA-256 over every fact key and row hash; equal fingerprints mean identical fact content."""
    conn = connect(db)
    rows = conn.execute("SELECT soc_code, naics_code, year, row_hash FROM fact_oews_estimate "
                        "ORDER BY soc_code, naics_code, year").fetchall()
    conn.close()
    return hashlib.sha256("\n".join("|".join(map(str, tuple(r))) for r in rows).encode()).hexdigest()[:16]


def rejects_per_run(db: Path) -> dict[int, int]:
    """Return {run_id: rejected row count} from rejected_record."""
    conn = connect(db)
    out = {r[0]: r[1] for r in conn.execute("SELECT run_id, COUNT(*) FROM rejected_record GROUP BY run_id")}
    conn.close()
    return out


def run_check(source_mode: str = "sample", db_path: Path | None = None,
              md_path: Path = DOCS_DIR / "RERUN_CHECK.md") -> bool:
    """Run the pipeline twice on a fresh database, verify nothing duplicated or drifted, and write RERUN_CHECK.md. Returns True if every check passes."""
    db_path = db_path or PROJECT_ROOT / "data" / "processed" / "rerun_check.db"
    for p in [db_path, Path(str(db_path) + "-journal")]:
        if p.exists():
            p.unlink()

    r1 = run_pipeline(source_mode, db_path=db_path, report_md=None)
    fp1 = fact_fingerprint(db_path)
    r2 = run_pipeline(source_mode, db_path=db_path, report_md=None)
    fp2 = fact_fingerprint(db_path)
    rj = rejects_per_run(db_path)
    c1, c2 = r1["table_counts"], r2["table_counts"]
    o2 = r2["load_outcome"]

    checks = [
        ("Analytic table row counts identical after run 2", all(c1[t] == c2[t] for t in ANALYTIC_TABLES)),
        ("Run 2 inserted 0 facts", o2["inserted"] == 0),
        ("Run 2 updated 0 facts", o2["updated"] == 0),
        ("Run 2 left every fact unchanged", o2["unchanged"] == c1["fact_oews_estimate"]),
        ("Fact content fingerprint identical", fp1 == fp2),
        ("Same number of records rejected in each run", len(set(rj.values())) == 1),
        ("Audit tables grew by exactly one run's batch",
         c2["etl_run"] == c1["etl_run"] + 1 and c2["source_file_log"] == 2 * c1["source_file_log"]
         and c2["rejected_record"] == 2 * c1["rejected_record"]),
    ]
    passed = all(ok for _, ok in checks)

    lines = [
        "# Re-runnability Check",
        "",
        f"Command: `uv run oews-pipeline rerun-check --source {source_mode}`  ",
        f"Executed: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()} UTC on a fresh database "
        f"(`{db_path.relative_to(PROJECT_ROOT) if db_path.is_relative_to(PROJECT_ROOT) else db_path}`).",
        "",
        "The pipeline was run twice against identical inputs. Analytic tables use natural-key upserts with "
        "row-hash change detection, so the second run must insert and update nothing. Audit tables "
        "(`etl_run`, `source_file_log`, `rejected_record`) intentionally append one batch per run so each "
        "run's lineage and rejects stay traceable.",
        "",
        "| table | after run 1 | after run 2 | expected |",
        "|---|---|---|---|",
    ]
    for t in ANALYTIC_TABLES:
        lines.append(f"| {t} | {c1[t]} | {c2[t]} | unchanged |")
    for t in AUDIT_TABLES:
        lines.append(f"| {t} | {c1[t]} | {c2[t]} | +1 run batch |")
    lines += [
        "",
        f"Run 2 fact load: inserted **{o2['inserted']}**, updated **{o2['updated']}**, unchanged **{o2['unchanged']}**, "
        f"stale keys **{o2['stale_keys_not_in_source']}**.  ",
        f"Fact fingerprint (SHA-256 of keys + row hashes): run 1 `{fp1}`, run 2 `{fp2}`.  ",
        f"Rejected records per run: {rj}.",
        "",
        "| check | result |",
        "|---|---|",
    ]
    lines += [f"| {name} | {'PASS' if ok else 'FAIL'} |" for name, ok in checks]
    lines += ["", f"**Overall: {'PASS' if passed else 'FAIL'}**", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("re-runnability check %s; written to %s", "PASSED" if passed else "FAILED", md_path)
    return passed
