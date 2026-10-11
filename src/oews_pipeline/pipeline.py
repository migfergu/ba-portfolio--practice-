"""End-to-end orchestration: extract -> transform/validate -> load (one transaction) -> quality report."""
from __future__ import annotations

import logging
import sqlite3
import traceback
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import extract, load, quality, transform
from .config import DEFAULT_DB, DOCS_DIR, REPORT_DIR, check_files_exist, load_settings
from .schema import connect, create_schema, table_counts
from .validate import RejectLog

log = logging.getLogger(__name__)


def _now() -> str:
    """Current UTC time as an ISO-8601 string (seconds precision)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_pipeline(source_mode: str = "sample", db_path: Path = DEFAULT_DB, data_dir: Path | None = None,
                 report_md: Path | None = DOCS_DIR / "QUALITY_REPORT.md",
                 report_json_dir: Path = REPORT_DIR) -> dict:
    """Build or refresh the database. Returns a summary dict. Raises on failure (after logging it)."""
    settings = load_settings(source_mode, data_dir=data_dir)
    check_files_exist(settings)

    conn = connect(db_path)
    create_schema(conn)
    started = _now()
    run_id = conn.execute("INSERT INTO etl_run (started_at, status, source_mode) VALUES (?, 'running', ?)",
                          (started, source_mode)).lastrowid
    conn.commit()
    log.info("run %d started (source=%s, db=%s)", run_id, source_mode, db_path)

    try:
        rejects = RejectLog()
        source_stats: dict = {}
        file_log: list[tuple] = []

        # ---- Extract + transform OEWS (one file per May reference year)
        frames = []
        for year, src in sorted(settings.oews_files.items()):
            ex = extract.extract_oews(src)
            res = transform.transform_oews(ex, settings, rejects)
            frames.append(res.records)
            source_stats[src.name] = res.stats
            file_log.append((run_id, src.name, src.path.name, src.version, ex.sha256, ex.size_bytes, len(ex.frame)))
        oews = pd.concat(frames, ignore_index=True)
        panel_socs = set(oews["soc_code"])

        # ---- Occupation-level external sources
        ex_e = extract.extract_exposure(settings.exposure_file, settings.exposure_measure)
        exposure, source_stats["exposure"] = transform.transform_exposure(ex_e, settings, panel_socs, rejects)
        file_log.append((run_id, "exposure", ex_e.source.path.name, ex_e.source.version, ex_e.sha256,
                         ex_e.size_bytes, len(ex_e.frame)))

        ex_j = extract.extract_job_zones(settings.job_zones_file)
        job_zones, source_stats["job_zones"] = transform.transform_job_zones(ex_j, panel_socs, rejects)
        file_log.append((run_id, "job_zones", ex_j.source.path.name, ex_j.source.version, ex_j.sha256,
                         ex_j.size_bytes, len(ex_j.frame)))

        dims = transform.build_dimensions(oews, settings)

        # ---- Load: everything in one transaction so a failure leaves the prior database intact
        with conn:
            load.upsert(conn, "dim_year", dims["dim_year"], ["year"])
            load.upsert(conn, "dim_occupation", dims["dim_occupation"], ["soc_code"])
            load.upsert(conn, "dim_industry", dims["dim_industry"], ["naics_code"])
            load.upsert(conn, "occupation_exposure", exposure[
                ["soc_code", "exposure_alpha", "exposure_beta", "exposure_gamma", "exposure_main",
                 "exposure_z", "measure", "n_onet_codes", "source_version"]], ["soc_code"])
            load.upsert(conn, "occupation_preparation", job_zones[
                ["soc_code", "job_zone_mean", "job_zone_max", "n_onet_codes", "onet_version"]], ["soc_code"])
            outcome = load.load_facts(conn, oews.drop(columns=["occ_title", "naics_title", "industry_level"]), run_id)
            load.write_rejects(conn, rejects.rows, run_id)
            conn.executemany("INSERT INTO source_file_log VALUES (?, ?, ?, ?, ?, ?, ?)", file_log)
            conn.execute("UPDATE etl_run SET status='succeeded', finished_at=?, facts_inserted=?, facts_updated=?, "
                         "facts_unchanged=?, rows_rejected=? WHERE run_id=?",
                         (_now(), outcome["inserted"], outcome["updated"], outcome["unchanged"], len(rejects), run_id))

        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            raise RuntimeError(f"{len(fk)} foreign-key violations after load")

        counts = table_counts(conn)
        run_state = {"source_mode": source_mode, "started_at": started, "source_stats": source_stats,
                     "load_outcome": outcome, "table_counts": counts}
        rep = quality.build_report(conn, run_id, run_state)
        if report_md is not None:
            jpath, mpath = quality.write_report(rep, report_json_dir, report_md)
            log.info("quality report written: %s and %s", mpath, jpath)
        log.info("run %d succeeded: %d facts in database, %d rows rejected", run_id,
                 counts["fact_oews_estimate"], len(rejects))
        return {"run_id": run_id, "load_outcome": outcome, "table_counts": counts,
                "rows_rejected": len(rejects), "report": rep}

    except Exception as exc:
        log.error("run %d failed: %s\n%s", run_id, exc, traceback.format_exc())
        try:
            conn.execute("UPDATE etl_run SET status='failed', finished_at=?, error_message=? WHERE run_id=?",
                         (_now(), str(exc)[:2000], run_id))
            conn.commit()
        except sqlite3.Error:
            log.exception("could not record failure in etl_run")
        raise
    finally:
        conn.close()
