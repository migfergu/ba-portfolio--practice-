"""Tests for parsing rules, validation routing, idempotent loading, and failure handling.

Run with: uv run pytest -q
"""
from __future__ import annotations

import csv
import sqlite3

import pytest

from oews_pipeline.config import ConfigError, SAMPLE_DIR
from oews_pipeline.pipeline import run_pipeline
from oews_pipeline.sample_data import generate
from oews_pipeline.transform import ParseError, normalize_naics, onet_to_soc, parse_number


# ---------- unit: BLS parsing conventions ----------
def test_parse_number_handles_bls_symbols_and_commas():
    assert parse_number("12,340", "TOT_EMP", {"**"}, as_int=True) == 12340
    assert parse_number("**", "TOT_EMP", {"**"}, as_int=True) is None
    assert parse_number("#", "A_MEAN", {"*", "#"}) is None
    assert parse_number("", "A_MEAN") is None
    with pytest.raises(ParseError):
        parse_number("n/a", "TOT_EMP", {"**"}, as_int=True)
    with pytest.raises(ParseError):
        parse_number("12.5", "TOT_EMP", as_int=True)


def test_code_normalization():
    assert normalize_naics("5221") == "522100"
    assert normalize_naics("522100.0") == "522100"
    assert onet_to_soc("13-2051.01") == "13-2051"


# ---------- integration: full pipeline on a private copy of the sample ----------
@pytest.fixture()
def sample_dir(tmp_path):
    d = tmp_path / "sample"
    generate(d)
    return d


def _run(sample_dir, db):
    return run_pipeline("sample", db_path=db, data_dir=sample_dir, report_md=None, report_json_dir=db.parent)


def test_pipeline_loads_and_quarantines_bad_rows(sample_dir, tmp_path):
    db = tmp_path / "t.db"
    res = _run(sample_dir, db)
    conn = sqlite3.connect(db)
    reasons = {r[0] for r in conn.execute("SELECT DISTINCT reason_code FROM rejected_record")}
    assert {"NON_NUMERIC", "DUPLICATE_EXACT", "DUPLICATE_CONFLICT", "INVALID_SOC",
            "RANGE", "MISSING_REQUIRED", "INVALID_ONET"} <= reasons
    # no fact key duplicated, no FK violations, suppression kept as NULL + flag
    assert conn.execute("SELECT COUNT(*) FROM (SELECT 1 FROM fact_oews_estimate GROUP BY soc_code, naics_code, year "
                        "HAVING COUNT(*) > 1)").fetchone()[0] == 0
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("SELECT COUNT(*) FROM fact_oews_estimate WHERE emp_suppressed = 1 AND tot_emp IS NOT NULL"
                        ).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM fact_oews_estimate WHERE emp_suppressed = 1").fetchone()[0] > 0
    # out-of-grain aggregate rows never reach the fact table
    assert conn.execute("SELECT COUNT(*) FROM fact_oews_estimate WHERE soc_code LIKE '%-0000'").fetchone()[0] == 0
    # every source reconciles
    assert all(r["reconciles"] for r in res["report"]["row_reconciliation"])


def test_second_run_is_idempotent(sample_dir, tmp_path):
    db = tmp_path / "t.db"
    first = _run(sample_dir, db)
    second = _run(sample_dir, db)
    assert second["load_outcome"]["inserted"] == 0
    assert second["load_outcome"]["updated"] == 0
    assert second["table_counts"]["fact_oews_estimate"] == first["table_counts"]["fact_oews_estimate"]


def test_refresh_updates_only_changed_rows(sample_dir, tmp_path):
    db = tmp_path / "t.db"
    _run(sample_dir, db)
    f = sample_dir / "oews_nat4d_M2025_sample.csv"
    with open(f, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    # bump employment by 1 on the last clean detailed 4-digit row (column 11 = TOT_EMP)
    idx = max(i for i, r in enumerate(rows[1:], 1)
              if r[6] == "4-digit" and r[10] == "detailed" and r[11].replace(",", "").isdigit())
    rows[idx][11] = str(int(rows[idx][11].replace(",", "")) + 1)
    with open(f, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    res = _run(sample_dir, db)
    assert res["load_outcome"]["inserted"] == 0
    assert res["load_outcome"]["updated"] == 1


def test_missing_file_fails_fast(tmp_path):
    with pytest.raises(ConfigError):
        run_pipeline("sample", db_path=tmp_path / "t.db", data_dir=tmp_path / "empty", report_md=None)


def test_failed_run_is_recorded_and_db_left_intact(sample_dir, tmp_path):
    db = tmp_path / "t.db"
    _run(sample_dir, db)
    before = sqlite3.connect(db).execute("SELECT COUNT(*) FROM fact_oews_estimate").fetchone()[0]
    bad = sample_dir / "oews_nat4d_M2023_sample.csv"
    bad.write_text("NOT,A,REAL,FILE\n1,2,3,4\n")
    with pytest.raises(Exception):
        _run(sample_dir, db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT status FROM etl_run ORDER BY run_id DESC LIMIT 1").fetchone()[0] == "failed"
    assert conn.execute("SELECT COUNT(*) FROM fact_oews_estimate").fetchone()[0] == before


def test_committed_sample_matches_generator(tmp_path):
    """The committed sample is reproducible from code (no hand-edited data)."""
    d = tmp_path / "regen"
    generate(d)
    for p in d.iterdir():
        assert (SAMPLE_DIR / p.name).read_bytes() == p.read_bytes(), p.name
