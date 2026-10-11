"""SQLite schema (3NF star schema + audit tables) and connection helper."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DDL = """
PRAGMA foreign_keys = ON;

-- ---------- Dimensions ----------
CREATE TABLE IF NOT EXISTS dim_occupation (
    soc_code      TEXT PRIMARY KEY CHECK (soc_code GLOB '[0-9][0-9]-[0-9][0-9][0-9][0-9]'),
    occ_title     TEXT NOT NULL,
    major_group   TEXT NOT NULL CHECK (major_group GLOB '[0-9][0-9]-0000'),
    focal_role    TEXT CHECK (focal_role IN ('analyst', 'clerk_contrast')),
    soc_vintage   TEXT NOT NULL DEFAULT '2018 SOC'
);

CREATE TABLE IF NOT EXISTS dim_industry (
    naics_code     TEXT PRIMARY KEY CHECK (length(naics_code) = 6),
    naics_title    TEXT NOT NULL,
    industry_level TEXT NOT NULL,
    naics_sector   TEXT NOT NULL CHECK (length(naics_sector) = 2)
);

CREATE TABLE IF NOT EXISTS dim_year (
    year            INTEGER PRIMARY KEY CHECK (year BETWEEN 2000 AND 2100),
    period          TEXT    NOT NULL CHECK (period IN ('pre', 'post')),
    post            INTEGER NOT NULL CHECK (post IN (0, 1)),
    post_delayed    INTEGER NOT NULL CHECK (post_delayed IN (0, 1)),
    reference_month TEXT    NOT NULL DEFAULT 'May'
);

-- ---------- Occupation attributes from external sources (1:1 optional with dim_occupation) ----------
CREATE TABLE IF NOT EXISTS occupation_exposure (
    soc_code        TEXT PRIMARY KEY REFERENCES dim_occupation(soc_code),
    exposure_alpha  REAL CHECK (exposure_alpha BETWEEN 0 AND 1),
    exposure_beta   REAL CHECK (exposure_beta  BETWEEN 0 AND 1),
    exposure_gamma  REAL CHECK (exposure_gamma BETWEEN 0 AND 1),
    exposure_main   REAL NOT NULL CHECK (exposure_main BETWEEN 0 AND 1),
    exposure_z      REAL NOT NULL,
    measure         TEXT NOT NULL,
    n_onet_codes    INTEGER NOT NULL CHECK (n_onet_codes >= 1),
    source_version  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS occupation_preparation (
    soc_code       TEXT PRIMARY KEY REFERENCES dim_occupation(soc_code),
    job_zone_mean  REAL    NOT NULL CHECK (job_zone_mean BETWEEN 1 AND 5),
    job_zone_max   INTEGER NOT NULL CHECK (job_zone_max BETWEEN 1 AND 5),
    n_onet_codes   INTEGER NOT NULL CHECK (n_onet_codes >= 1),
    onet_version   TEXT    NOT NULL
);

-- ---------- Fact: one row per occupation x industry x May reference year ----------
CREATE TABLE IF NOT EXISTS fact_oews_estimate (
    soc_code          TEXT    NOT NULL REFERENCES dim_occupation(soc_code),
    naics_code        TEXT    NOT NULL REFERENCES dim_industry(naics_code),
    year              INTEGER NOT NULL REFERENCES dim_year(year),
    tot_emp           INTEGER CHECK (tot_emp >= 0),
    emp_prse          REAL    CHECK (emp_prse >= 0),
    a_mean            REAL    CHECK (a_mean > 0),
    h_mean            REAL    CHECK (h_mean > 0),
    mean_prse         REAL    CHECK (mean_prse >= 0),
    emp_suppressed    INTEGER NOT NULL CHECK (emp_suppressed IN (0, 1)),
    wage_suppressed   INTEGER NOT NULL CHECK (wage_suppressed IN (0, 1)),
    wage_topcoded     INTEGER NOT NULL CHECK (wage_topcoded IN (0, 1)),
    source_file       TEXT    NOT NULL,
    row_hash          TEXT    NOT NULL,
    first_loaded_run  INTEGER NOT NULL REFERENCES etl_run(run_id),
    last_changed_run  INTEGER NOT NULL REFERENCES etl_run(run_id),
    PRIMARY KEY (soc_code, naics_code, year)
);
CREATE INDEX IF NOT EXISTS ix_fact_year_naics ON fact_oews_estimate(year, naics_code);  -- industry-by-year slices
CREATE INDEX IF NOT EXISTS ix_fact_naics_soc ON fact_oews_estimate(naics_code, soc_code); -- occupation-by-industry cells across years

-- ---------- Audit / lineage ----------
CREATE TABLE IF NOT EXISTS etl_run (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    source_mode   TEXT NOT NULL CHECK (source_mode IN ('sample', 'raw')),
    facts_inserted  INTEGER,
    facts_updated   INTEGER,
    facts_unchanged INTEGER,
    rows_rejected   INTEGER,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS source_file_log (
    run_id       INTEGER NOT NULL REFERENCES etl_run(run_id),
    source_name  TEXT    NOT NULL,
    file_name    TEXT    NOT NULL,
    version      TEXT,
    sha256       TEXT    NOT NULL,
    size_bytes   INTEGER NOT NULL,
    rows_read    INTEGER NOT NULL,
    PRIMARY KEY (run_id, source_name)
);

CREATE TABLE IF NOT EXISTS rejected_record (
    reject_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       INTEGER NOT NULL REFERENCES etl_run(run_id),
    source_name  TEXT    NOT NULL,
    record_key   TEXT,
    reason_code  TEXT    NOT NULL,
    detail       TEXT,
    raw_record   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_reject_run ON rejected_record(run_id, reason_code);

-- ---------- Analysis-ready view (consumed by A5+ modeling) ----------
DROP VIEW IF EXISTS v_analysis_panel;
CREATE VIEW v_analysis_panel AS
SELECT f.soc_code, o.occ_title, o.major_group, o.focal_role,
       f.naics_code, i.naics_title, i.naics_sector,
       f.year, y.period, y.post, y.post_delayed,
       f.tot_emp, f.a_mean, f.emp_prse, f.mean_prse,
       f.emp_suppressed, f.wage_suppressed, f.wage_topcoded,
       e.exposure_main, e.exposure_z, e.measure AS exposure_measure,
       p.job_zone_mean,
       e.exposure_z * y.post AS exposure_x_post,
       CASE WHEN f.tot_emp IS NOT NULL AND e.exposure_z IS NOT NULL THEN 1 ELSE 0 END AS emp_model_ready,
       CASE WHEN f.a_mean  IS NOT NULL AND e.exposure_z IS NOT NULL THEN 1 ELSE 0 END AS wage_model_ready
FROM fact_oews_estimate f
JOIN dim_occupation o ON o.soc_code = f.soc_code
JOIN dim_industry   i ON i.naics_code = f.naics_code
JOIN dim_year       y ON y.year = f.year
LEFT JOIN occupation_exposure    e ON e.soc_code = f.soc_code
LEFT JOIN occupation_preparation p ON p.soc_code = f.soc_code;
"""

TABLES = ["dim_occupation", "dim_industry", "dim_year", "occupation_exposure",
          "occupation_preparation", "fact_oews_estimate", "etl_run",
          "source_file_log", "rejected_record"]


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (creating folders if needed) a SQLite connection with foreign keys enforced."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables, indexes, and the analysis view if they do not already exist."""
    conn.executescript(DDL)
    conn.commit()


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return row counts for every table in TABLES."""
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
